"""Suspicious-activity-response detector.

Inspects every `aws_cloudwatch_event_rule` resource and reports whether
its `event_pattern` matches the GuardDuty (or Security Hub or
IAM Access Analyzer) finding source — i.e. whether the customer has
wired an EventBridge rule to fire on a security finding. Then joins
`aws_cloudwatch_event_target` to verify there's actually a Lambda /
SNS / SQS / Step Functions destination that handles the event.

A finding-firing EventBridge rule with a real target IS the canonical
IaC-evidenceable "automated response to suspicious activity" signal.
KSI-IAM-SUS ("Responding to Suspicious Activity") asks customers to
"automatically disable or otherwise secure accounts with privileged
access in response to suspicious activity" — the EventBridge-rule-plus-
target pattern is precisely the AWS-recommended way to express this in
infrastructure.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-IAM-SUS lists `ac-2`, `ac-2.1`, `ac-2.3`, `ac-2.13` (Disable
    Accounts for High-Risk Individuals), `ac-7`, `ps-4`, `ps-8`. The
    EventBridge-rule-plus-target pattern evidences AC-2(13) directly
    — automated account-state response to suspicious activity. The
    detector also evidences AC-2 (Account Management) at the framing
    layer.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

# Sources whose findings warrant an automated response. Each is a
# canonical AWS suspicious-activity signal; matching any of them in a
# rule's `event_pattern` "source" field counts.
_SECURITY_FINDING_SOURCES: tuple[str, ...] = (
    "aws.guardduty",
    "aws.securityhub",
    "aws.access-analyzer",
    "aws.inspector2",
    "aws.macie2",
)


@detector(
    id="aws.suspicious_activity_response",
    ksis=["KSI-IAM-SUS"],
    controls=["AC-2", "AC-2(13)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one Evidence per finding-sourced EventBridge rule.

    Evidences (800-53):  AC-2 (Account Management — at the framing
                         layer); AC-2(13) (Disable Accounts for
                         High-Risk Individuals — automated account-
                         state response is the canonical mechanism).
    Evidences (KSI):     KSI-IAM-SUS (Responding to Suspicious Activity).
    Does NOT prove:      that the target Lambda/SNS actually disables
                         accounts (vs. merely logging the event); that
                         the target is wired correctly; that the
                         target's IAM role can take the disable action.
                         The detector establishes the architectural
                         pattern is in place; runtime correctness is
                         a separate concern.
    """
    targets_by_rule: dict[str, list[TerraformResource]] = {}
    rules: list[TerraformResource] = []

    for r in resources:
        if r.type == "aws_cloudwatch_event_rule":
            rules.append(r)
        elif r.type == "aws_cloudwatch_event_target":
            rule_name = _rule_name_ref(r.body.get("rule"))
            if rule_name:
                targets_by_rule.setdefault(rule_name, []).append(r)

    out: list[Evidence] = []
    now = datetime.now(UTC)
    for rule in rules:
        sources = _matched_finding_sources(rule.body)
        if not sources:
            continue
        attached = targets_by_rule.get(rule.name, [])
        out.append(_emit_rule_evidence(rule, sources, attached, now))

    return out


def _emit_rule_evidence(
    rule: TerraformResource,
    sources: list[str],
    targets: list[TerraformResource],
    now: datetime,
) -> Evidence:
    """Build one Evidence record characterizing the rule's response posture."""
    target_count = len(targets)
    response_state = "wired" if target_count > 0 else "no_target"

    content: dict[str, Any] = {
        "resource_type": rule.type,
        "resource_name": rule.name,
        "response_state": response_state,
        "matched_sources": sources,
        "target_count": target_count,
        "target_summary": [_target_kind(t) for t in targets],
    }

    if response_state == "no_target":
        content["gap"] = (
            f"EventBridge rule `{rule.name}` matches "
            f"{', '.join(sources)} findings but has no "
            "`aws_cloudwatch_event_target` attached. The rule fires "
            "but no automated response runs; KSI-IAM-SUS asks for "
            "the response, not just the trigger."
        )

    return Evidence.create(
        detector_id="aws.suspicious_activity_response",
        ksis_evidenced=["KSI-IAM-SUS"],
        controls_evidenced=["AC-2", "AC-2(13)"],
        source_ref=rule.source_ref,
        content=content,
        timestamp=now,
    )


def _matched_finding_sources(body: dict[str, Any]) -> list[str]:
    """Return the security-finding sources matched by this rule's event_pattern.

    `event_pattern` is HCL-rendered three ways:
      1. An inline JSON-literal string (rare in practice).
      2. A `${jsonencode({...})}` placeholder — the canonical Terraform
         shape. python-hcl2 keeps the raw expression body inside the
         placeholder, including the `source` field's value list. We
         substring-match the known security-finding source strings.
      3. A `${data.x.y}` or `${file(...)}` placeholder where the body is
         not present at the HCL layer — yields no matches in HCL mode.
         Plan-JSON mode resolves these.
    """
    pattern = _as_str(body.get("event_pattern"))
    if pattern is None:
        return []

    # Case 1: literal JSON.
    if not pattern.startswith("${"):
        try:
            parsed = json.loads(pattern)
        except json.JSONDecodeError:
            return []
        sources_raw = parsed.get("source") if isinstance(parsed, dict) else None
        if isinstance(sources_raw, str):
            sources_raw = [sources_raw]
        if not isinstance(sources_raw, list):
            return []
        return sorted({s for s in sources_raw if s in _SECURITY_FINDING_SOURCES})

    # Case 2: jsonencode placeholder. Substring-match the source list.
    # Only count matches if the placeholder is from `jsonencode(...)` —
    # other indirections (file(), data refs) don't expose the source
    # in-line.
    if "jsonencode" not in pattern:
        return []
    return sorted({s for s in _SECURITY_FINDING_SOURCES if s in pattern})


def _rule_name_ref(value: Any) -> str | None:
    """`rule = aws_cloudwatch_event_rule.foo.name` — pull the rule name out."""
    s = _as_str(value)
    if s is None:
        return None
    marker = "aws_cloudwatch_event_rule."
    idx = s.find(marker)
    if idx < 0:
        return None
    rest = s[idx + len(marker) :]
    return rest.split(".", 1)[0].rstrip("}").rstrip()


def _target_kind(target: TerraformResource) -> str:
    """Best-effort classification of the target's destination kind from arn."""
    arn = _as_str(target.body.get("arn")) or ""
    for kind, prefix in (
        ("lambda", "arn:aws:lambda"),
        ("sns", "arn:aws:sns"),
        ("sqs", "arn:aws:sqs"),
        ("states", "arn:aws:states"),
        ("ssm-automation", "arn:aws:ssm:"),
    ):
        if prefix in arn:
            return kind
    return "other"


def _as_str(value: Any) -> str | None:
    """python-hcl2 occasionally returns strings wrapped in single-element lists."""
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value if isinstance(value, str) else None
