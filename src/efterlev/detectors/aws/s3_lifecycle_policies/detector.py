"""S3 lifecycle-policies detector.

Looks for `aws_s3_bucket_lifecycle_configuration` resources and reports
whether the bucket has rules that expire or transition objects. KSI-
SVC-RUD ("Removing Unwanted Data") asks the customer to remove unwanted
data on a defined cadence; S3 bucket lifecycle policies are the
canonical IaC-evidenceable signal — they declare exactly what gets
expired, after how many days, and into which storage class.

A lifecycle config without any rules (or rules without expiration /
transition blocks) is a config-shaped no-op; the detector flags this
explicitly so a reviewer can distinguish "rules in place" from
"placeholder config."

KSI mapping per FRMR 0.9.43-beta:
  - KSI-SVC-RUD lists `si-12.3` and `si-18.4` in its `controls` array.
    This detector evidences SI-12 (Information Management and
    Retention) and SI-12(3) (Destruction — secure removal of data
    no longer needed). SI-18.4 is a PII-data-quality control adjacent
    but not directly evidenced by lifecycle config alone.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.s3_lifecycle_policies",
    ksis=["KSI-SVC-RUD"],
    controls=["SI-12", "SI-12(3)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one Evidence per `aws_s3_bucket_lifecycle_configuration`.

    Evidences (800-53):  SI-12 (Information Management and Retention) at
                         the structural-declaration level when a lifecycle
                         configuration is declared. SI-12(3) (Destruction)
                         when at least one rule has an `expiration` block.
    Evidences (KSI):     KSI-SVC-RUD (Removing Unwanted Data).
    Does NOT prove:      that the retention period matches the customer's
                         policy or FedRAMP requirement (that's a per-
                         organization risk decision); that lifecycle
                         actions actually run (operational concern); or
                         that PII is identified before deletion (SI-18.4
                         data-quality territory, separate detector).
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_s3_bucket_lifecycle_configuration":
            continue
        out.append(_emit_evidence(r, now))

    return out


def _emit_evidence(r: TerraformResource, now: datetime) -> Evidence:
    """Characterize one lifecycle configuration resource."""
    rule_blocks = _normalize_blocks(r.body.get("rule"))
    expiration_rule_count = sum(1 for b in rule_blocks if _has_expiration(b))
    transition_rule_count = sum(1 for b in rule_blocks if _has_transition(b))
    enabled_rule_count = sum(1 for b in rule_blocks if _is_enabled(b))
    total_rules = len(rule_blocks)

    if expiration_rule_count > 0 and enabled_rule_count > 0:
        lifecycle_state = "configured_with_expiration"
        controls = ["SI-12", "SI-12(3)"]
    elif total_rules > 0 and enabled_rule_count > 0:
        lifecycle_state = "configured_no_expiration"
        controls = ["SI-12"]
    else:
        lifecycle_state = "placeholder"
        controls = ["SI-12"]

    bucket_ref = _coerce_str(r.body.get("bucket"))
    content: dict[str, Any] = {
        "resource_type": r.type,
        "resource_name": r.name,
        "bucket_ref": bucket_ref,
        "rule_count": total_rules,
        "enabled_rule_count": enabled_rule_count,
        "expiration_rule_count": expiration_rule_count,
        "transition_rule_count": transition_rule_count,
        "lifecycle_state": lifecycle_state,
    }
    if lifecycle_state == "configured_no_expiration":
        content["gap"] = (
            "Lifecycle configuration has rules but none with an `expiration` block — "
            "transitions alone (e.g. STANDARD_IA → GLACIER) reduce cost but do not "
            "evidence SI-12(3) Destruction. Add an expiration rule to evidence "
            "KSI-SVC-RUD's data-removal commitment."
        )
    elif lifecycle_state == "placeholder":
        content["gap"] = (
            "Lifecycle configuration declared but no enabled rules with retention or "
            "transition actions. The resource is a placeholder; SI-12 is not "
            "evidenced beyond the structural declaration."
        )

    return Evidence.create(
        detector_id="aws.s3_lifecycle_policies",
        ksis_evidenced=["KSI-SVC-RUD"],
        controls_evidenced=controls,
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )


def _normalize_blocks(value: Any) -> list[dict[str, Any]]:
    """python-hcl2 yields repeated `rule {}` blocks as a list; single-block as dict."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [b for b in value if isinstance(b, dict)]
    return []


def _has_expiration(rule: dict[str, Any]) -> bool:
    expiration = rule.get("expiration")
    return expiration is not None and (isinstance(expiration, (dict, list)))


def _has_transition(rule: dict[str, Any]) -> bool:
    transition = rule.get("transition")
    return transition is not None and (isinstance(transition, (dict, list)))


def _is_enabled(rule: dict[str, Any]) -> bool:
    """A rule with `status` field equal to "Enabled" is active. Default in
    AWS is also "Enabled" when status is omitted, so absent → active."""
    status = rule.get("status")
    if status is None:
        return True
    if isinstance(status, str):
        return status.lower() == "enabled"
    return False


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
