"""Secrets Manager rotation detector.

Inspects `aws_secretsmanager_secret_rotation` resources. Captures the
rotation window (`automatically_after_days`) and the rotation Lambda
ARN. Emits per-rotation evidence; secrets without rotation resources
are not directly visible to this detector — they're emitted as a
negative shape only when they have a corresponding `aws_secretsmanager_secret`
declared without a paired rotation.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-SVC-ASM (Automating Secret Management) — sc-12 is listed.
  - KSI-IAM-SNU (Securing Non-User Authentication) — ia-5 is listed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

# AWS Secrets Manager allows rotation up to 365 days; FedRAMP recommends
# rotation at most every 90 days for credentials.
_RECOMMENDED_MAX_DAYS = 90


@detector(
    id="aws.secrets_manager_rotation",
    ksis=["KSI-SVC-ASM", "KSI-IAM-SNU"],
    controls=["SC-12", "IA-5(1)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit per-secret rotation evidence.

    Evidences (800-53):  SC-12 (Cryptographic Key Management),
                         IA-5(1) (Authenticator Management — Lifecycle).
    Evidences (KSI):     KSI-SVC-ASM, KSI-IAM-SNU.
    Does NOT prove:      that the rotation Lambda is correctly
                         implemented (that's a code review, not an
                         IaC scan); that all secrets are rotated
                         (only those with explicit rotation resources
                         are visible); that the rotation actually
                         executes successfully at runtime.
    """
    rotations: dict[str, TerraformResource] = {}
    secrets: list[TerraformResource] = []

    for r in resources:
        if r.type == "aws_secretsmanager_secret_rotation":
            secret_id = _coerce_str(r.body.get("secret_id")) or r.name
            rotations[secret_id] = r
        elif r.type == "aws_secretsmanager_secret":
            secrets.append(r)

    out: list[Evidence] = []
    now = datetime.now(UTC)

    # Per-rotation evidence: positive if rotation present + within window.
    for r in rotations.values():
        out.append(_emit_rotation_evidence(r, now))

    # Per-secret negative evidence: secret declared without a paired rotation.
    for s in secrets:
        # Secret may be paired with a rotation by name or by reference like
        # `aws_secretsmanager_secret.foo.id`. We match by Terraform-resource
        # path heuristically; if any rotation references the secret name as
        # a substring of its secret_id, we treat them as paired.
        paired = any(s.name in (key or "") for key in rotations)
        if not paired:
            out.append(_emit_unrotated_secret_evidence(s, now))

    return out


def _emit_rotation_evidence(r: TerraformResource, now: datetime) -> Evidence:
    rules = r.get_nested("rotation_rules") if hasattr(r, "get_nested") else None
    days = None
    if isinstance(rules, dict):
        days = rules.get("automatically_after_days")

    days_int = _coerce_int(days)
    has_lambda = bool(_coerce_str(r.body.get("rotation_lambda_arn")))

    if days_int is None:
        rotation_state = "configured_unknown_window"
    elif days_int <= _RECOMMENDED_MAX_DAYS:
        rotation_state = "configured_within_recommended"
    else:
        rotation_state = "configured_window_too_long"

    content: dict[str, Any] = {
        "resource_type": "aws_secretsmanager_secret_rotation",
        "resource_name": r.name,
        "rotation_state": rotation_state,
        "automatically_after_days": days_int,
        "has_rotation_lambda": has_lambda,
    }
    if rotation_state == "configured_window_too_long":
        content["gap"] = (
            f"rotation window is {days_int} days; FedRAMP recommends "
            f"<= {_RECOMMENDED_MAX_DAYS} days for credential secrets"
        )
    return Evidence.create(
        detector_id="aws.secrets_manager_rotation",
        ksis_evidenced=["KSI-SVC-ASM", "KSI-IAM-SNU"],
        controls_evidenced=["SC-12", "IA-5(1)"],
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )


def _emit_unrotated_secret_evidence(s: TerraformResource, now: datetime) -> Evidence:
    return Evidence.create(
        detector_id="aws.secrets_manager_rotation",
        ksis_evidenced=["KSI-SVC-ASM", "KSI-IAM-SNU"],
        controls_evidenced=["SC-12", "IA-5(1)"],
        source_ref=s.source_ref,
        content={
            "resource_type": "aws_secretsmanager_secret",
            "resource_name": s.name,
            "rotation_state": "absent",
            "gap": "secret declared without a paired aws_secretsmanager_secret_rotation resource",
        },
        timestamp=now,
    )


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
