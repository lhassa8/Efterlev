"""IAM inline-policies audit detector.

Inventories inline-policy resources attached to IAM principals
(`aws_iam_role_policy`, `aws_iam_user_policy`, `aws_iam_group_policy`).
Inline policies are an anti-pattern compared to managed policies because
they're invisible from the IAM console outside the attached identity,
and they can't be reused or audited centrally. This detector surfaces
their presence as a hygiene signal — the Gap Agent reasons about
whether the inline use is justified.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-IAM-ELP (Ensuring Least Privilege) lists ac-2 and ac-6.
  - KSI-IAM-JIT (Authorizing Just-in-Time) lists ac-2 AND ac-6 — inline
    policies bypass central managed-policy review and are typically
    standing grants, the inverse of just-in-time authorization.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_INLINE_POLICY_TYPES: dict[str, str] = {
    "aws_iam_role_policy": "role",
    "aws_iam_user_policy": "user",
    "aws_iam_group_policy": "group",
}


@detector(
    id="aws.iam_inline_policies_audit",
    ksis=["KSI-IAM-ELP", "KSI-IAM-JIT"],
    controls=["AC-2", "AC-6"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence for each inline IAM policy attached to a principal.

    Evidences (800-53):  AC-2 (Account Management), AC-6 (Least Privilege).
    Evidences (KSI):     KSI-IAM-ELP (Ensuring Least Privilege),
                         KSI-IAM-JIT (Authorizing Just-in-Time) — both AC-2
                         and AC-6 overlap with JIT's controls; inline
                         policies on principals are the standing-grant
                         antithesis of just-in-time authorization.
    Does NOT prove:      that the inline policy is overly broad — its
                         contents render as a `${...}` placeholder when
                         built via jsonencode or data references; the
                         detector flags inline use as a hygiene signal,
                         not policy-content over-permissiveness.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        principal_kind = _INLINE_POLICY_TYPES.get(r.type)
        if principal_kind is None:
            continue
        out.append(_emit_inline_evidence(r, principal_kind, now))

    return out


def _emit_inline_evidence(
    r: TerraformResource,
    principal_kind: str,
    now: datetime,
) -> Evidence:
    body = r.body
    principal = _coerce_str(body.get(principal_kind))
    policy_value = body.get("policy")
    policy_state = (
        "literal_json"
        if isinstance(policy_value, str) and not policy_value.strip().startswith("${")
        else "unparseable"
    )

    return Evidence.create(
        detector_id="aws.iam_inline_policies_audit",
        ksis_evidenced=["KSI-IAM-ELP", "KSI-IAM-JIT"],
        controls_evidenced=["AC-2", "AC-6"],
        source_ref=r.source_ref,
        content={
            "resource_type": r.type,
            "resource_name": r.name,
            "principal_kind": principal_kind,
            "principal_ref": principal,
            "policy_state": policy_state,
            "policy_name": _coerce_str(body.get("name")),
        },
        timestamp=now,
    )


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
