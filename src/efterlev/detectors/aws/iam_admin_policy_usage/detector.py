"""IAM admin-policy-usage detector.

Flags every IAM principal (role, user, group) with the AWS-managed
`AdministratorAccess` policy attached. AdministratorAccess grants
`*:*` — full account control. Some principals legitimately need it
(emergency break-glass roles, deployment automation roles, organization
admin roles); the detector surfaces every attachment so the Gap Agent
can reason about justification per principal.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-IAM-ELP (Ensuring Least Privilege) lists ac-2 and ac-6.
  - KSI-IAM-JIT (Authorizing Just-in-Time) lists ac-6 (among others) —
    AdministratorAccess attached as a permanent grant is direct
    anti-JIT signal; the Gap Agent reasons over per-attachment
    duration/justification.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_ADMIN_POLICY_ARN = "arn:aws:iam::aws:policy/AdministratorAccess"

_ATTACHMENT_TYPES: dict[str, str] = {
    "aws_iam_role_policy_attachment": "role",
    "aws_iam_user_policy_attachment": "user",
    "aws_iam_group_policy_attachment": "group",
}


@detector(
    id="aws.iam_admin_policy_usage",
    ksis=["KSI-IAM-ELP", "KSI-IAM-JIT"],
    controls=["AC-6", "AC-6(2)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence per attachment of the AdministratorAccess managed policy.

    Evidences (800-53):  AC-6 (Least Privilege),
                         AC-6(2) (Privileged Functions / Non-Privileged Use).
    Evidences (KSI):     KSI-IAM-ELP (Ensuring Least Privilege),
                         KSI-IAM-JIT (Authorizing Just-in-Time) — AC-6
                         overlap; an AdministratorAccess attachment is
                         anti-JIT signal absent compensating controls.
    Does NOT prove:      that the principal is actually used at runtime;
                         that the privilege is unjustified — emergency
                         break-glass roles legitimately have this. The
                         Gap Agent makes the human-judgment call about
                         per-principal justification.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        principal_kind = _ATTACHMENT_TYPES.get(r.type)
        if principal_kind is None:
            continue
        policy_arn = _coerce_str(r.body.get("policy_arn"))
        if policy_arn != _ADMIN_POLICY_ARN:
            continue
        out.append(_emit_admin_attachment_evidence(r, principal_kind, now))

    return out


def _emit_admin_attachment_evidence(
    r: TerraformResource,
    principal_kind: str,
    now: datetime,
) -> Evidence:
    return Evidence.create(
        detector_id="aws.iam_admin_policy_usage",
        ksis_evidenced=["KSI-IAM-ELP", "KSI-IAM-JIT"],
        controls_evidenced=["AC-6", "AC-6(2)"],
        source_ref=r.source_ref,
        content={
            "resource_type": r.type,
            "resource_name": r.name,
            "principal_kind": principal_kind,
            "principal_ref": _coerce_str(r.body.get(principal_kind)),
            "policy_arn": _ADMIN_POLICY_ARN,
            "gap": (
                f"AdministratorAccess attached to {principal_kind} "
                f"{_coerce_str(r.body.get(principal_kind))!r}"
            ),
        },
        timestamp=now,
    )


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
