"""KMS customer-managed key inventory.

Inventories `aws_kms_key` resources (CMKs) declared in the Terraform.
Each key produces one Evidence record capturing its description, key
usage (encrypt/decrypt vs sign/verify), and (where set) deletion-window
days. Complements the existing `aws.kms_key_rotation` detector — that
one inspects per-key rotation status; this one establishes that CMKs
are present at all.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-SVC-ASM (Automating Secret Management) — sc-12 is listed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.kms_customer_managed_keys",
    ksis=["KSI-SVC-ASM"],
    controls=["SC-12"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence for each declared aws_kms_key.

    Evidences (800-53):  SC-12 (Cryptographic Key Establishment / Management).
    Evidences (KSI):     KSI-SVC-ASM (Automating Secret Management).
    Does NOT prove:      that the keys are actually used by the
                         resources that should use them; rotation policy
                         (covered by `aws.kms_key_rotation`); the
                         key-deletion lifecycle is appropriate.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_kms_key":
            continue
        out.append(_emit_cmk_evidence(r, now))

    return out


def _emit_cmk_evidence(r: TerraformResource, now: datetime) -> Evidence:
    body = r.body
    return Evidence.create(
        detector_id="aws.kms_customer_managed_keys",
        ksis_evidenced=["KSI-SVC-ASM"],
        controls_evidenced=["SC-12"],
        source_ref=r.source_ref,
        content={
            "resource_type": "aws_kms_key",
            "resource_name": r.name,
            "key_state": "declared",
            "description": _coerce_str(body.get("description")),
            "key_usage": _coerce_str(body.get("key_usage")) or "ENCRYPT_DECRYPT",
            "deletion_window_in_days": body.get("deletion_window_in_days"),
            "is_enabled": body.get("is_enabled", True),
        },
        timestamp=now,
    )


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
