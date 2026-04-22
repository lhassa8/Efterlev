"""RDS at-rest encryption detector.

Mirrors `encryption_s3_at_rest` for `aws_db_instance` resources: checks
the `storage_encrypted` attribute and, when present, records whether a
customer-managed KMS key (`kms_key_id`) is bound.

Per DECISIONS 2026-04-21 design call #1, Option C: FRMR 0.9.43-beta lists
no KSI whose `controls` array contains SC-28, so this detector declares
`ksis=[]` and surfaces at the 800-53 level only. The Gap Agent renders
such findings as "unmapped to any current KSI" — identical posture to
encryption_s3_at_rest, for the same reason.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.rds_encryption_at_rest",
    ksis=[],  # DECISIONS 2026-04-21: SC-28 has no FRMR KSI in 0.9.43-beta
    controls=["SC-28", "SC-28(1)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit encryption-state Evidence for every aws_db_instance found.

    Evidences (800-53):  SC-28 (Protection of Information at Rest).
                         SC-28(1) (Cryptographic Protection) when a KMS
                         key is bound (`kms_key_id`) or `storage_encrypted`
                         is declared true (AWS always uses AES-256 under
                         RDS at-rest encryption — naming the algorithm is
                         implicit).
    Evidences (KSI):     None — SC-28 is not currently mapped to any FRMR
                         KSI in 0.9.43-beta.
    Does NOT prove:      key rotation, BYOK governance, backup-snapshot
                         encryption (orthogonal setting, see
                         `aws_db_instance.copy_tags_to_snapshot` +
                         snapshot encryption posture), read-replica
                         encryption inheritance quirks, or runtime state
                         of deployed databases.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_db_instance":
            continue
        out.append(_emit_rds_evidence(r, now))
    return out


def _emit_rds_evidence(r: TerraformResource, now: datetime) -> Evidence:
    storage_encrypted = r.body.get("storage_encrypted")
    kms_key_id = r.body.get("kms_key_id")

    # HCL booleans arrive as native bool; a string "true" would be from a
    # variable / local and cannot be statically evaluated — we refuse to
    # guess, same policy as s3_public_access_block._coerce_bool.
    is_encrypted = storage_encrypted is True

    content: dict[str, Any] = {
        "resource_type": r.type,
        "resource_name": r.name,
    }

    if is_encrypted:
        content["encryption_state"] = "present"
        # AWS RDS at-rest encryption is always AES-256; naming it is safe.
        content["algorithm"] = "AES256"
        if isinstance(kms_key_id, str) and kms_key_id:
            content["key_management"] = "customer_managed"
            content["kms_key_id"] = kms_key_id
        else:
            content["key_management"] = "aws_managed"
        return Evidence.create(
            detector_id="aws.rds_encryption_at_rest",
            ksis_evidenced=[],
            controls_evidenced=["SC-28", "SC-28(1)"],
            source_ref=r.source_ref,
            content=content,
            timestamp=now,
        )

    content["encryption_state"] = "absent"
    content["gap"] = "storage_encrypted not set to true"
    return Evidence.create(
        detector_id="aws.rds_encryption_at_rest",
        ksis_evidenced=[],
        controls_evidenced=["SC-28"],
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )
