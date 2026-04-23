"""EBS volume at-rest encryption detector.

Parallels `encryption_s3_at_rest` and `rds_encryption_at_rest` for
`aws_ebs_volume` resources. Checks `encrypted` attribute and records
whether a customer-managed KMS key (`kms_key_id`) is bound.

Also detects `aws_instance.root_block_device` and
`aws_instance.ebs_block_device` blocks — EBS volumes attached inline
to an EC2 instance are as much part of the at-rest encryption surface
as standalone `aws_ebs_volume` resources, and many real codebases use
both patterns.

Per DECISIONS 2026-04-21 design call #1, Option C: FRMR 0.9.43-beta
lists no KSI whose `controls` array contains SC-28, so this detector
declares `ksis=[]` and surfaces at the 800-53 level only — same
rationale as the S3 and RDS at-rest encryption detectors.

Motivated by the 2026-04-22 dogfood pass: ground-truth gap #3
(govnotes `bastion_scratch` volume with `encrypted = false`) was
invisible without this detector.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.encryption_ebs",
    ksis=[],  # DECISIONS 2026-04-21: SC-28 has no FRMR KSI in 0.9.43-beta
    controls=["SC-28", "SC-28(1)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit encryption-state Evidence for every EBS-shaped volume found.

    Evidences (800-53):  SC-28 (Protection of Information at Rest).
                         SC-28(1) (Cryptographic Protection) when
                         encryption is enabled (AWS EBS at-rest
                         encryption always uses AES-256).
    Evidences (KSI):     None — SC-28 is not currently mapped to any FRMR
                         KSI in 0.9.43-beta.
    Does NOT prove:      key rotation (SC-12 — that's the
                         `kms_key_rotation` detector's territory),
                         BYOK governance, snapshot-encryption
                         inheritance on manual snapshots, or runtime
                         state of deployed volumes.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type == "aws_ebs_volume":
            out.append(_emit_standalone_ebs(r, now))
        elif r.type == "aws_instance":
            out.extend(_emit_instance_block_devices(r, now))
    return out


def _emit_standalone_ebs(r: TerraformResource, now: datetime) -> Evidence:
    is_encrypted = r.body.get("encrypted") is True
    kms_key_id = r.body.get("kms_key_id")
    return _build_evidence(
        location="standalone",
        resource_type=r.type,
        resource_name=r.name,
        is_encrypted=is_encrypted,
        kms_key_id=kms_key_id,
        source_ref=r.source_ref,
        now=now,
    )


def _emit_instance_block_devices(r: TerraformResource, now: datetime) -> list[Evidence]:
    """Emit one Evidence per root_block_device / ebs_block_device block.

    An `aws_instance` can declare an inline root volume and multiple
    additional data volumes. We treat each as its own at-rest-encryption
    finding so the Gap Agent sees the per-volume posture.
    """
    results: list[Evidence] = []
    for block_field in ("root_block_device", "ebs_block_device"):
        blocks = _coerce_block_list(r.body.get(block_field))
        for idx, block in enumerate(blocks):
            is_encrypted = block.get("encrypted") is True
            kms_key_id = block.get("kms_key_id")
            # Logical name differentiates which block produced the record
            # when an instance has multiple inline EBS blocks.
            sub_name = (
                f"{r.name}.{block_field}"
                if block_field == "root_block_device"
                else f"{r.name}.{block_field}[{idx}]"
            )
            results.append(
                _build_evidence(
                    location=block_field,
                    resource_type=r.type,
                    resource_name=sub_name,
                    is_encrypted=is_encrypted,
                    kms_key_id=kms_key_id,
                    source_ref=r.source_ref,
                    now=now,
                )
            )
    return results


def _build_evidence(
    *,
    location: str,
    resource_type: str,
    resource_name: str,
    is_encrypted: bool,
    kms_key_id: Any,
    source_ref: Any,
    now: datetime,
) -> Evidence:
    content: dict[str, Any] = {
        "resource_type": resource_type,
        "resource_name": resource_name,
        "location": location,
    }
    if is_encrypted:
        content["encryption_state"] = "present"
        content["algorithm"] = "AES256"
        if isinstance(kms_key_id, str) and kms_key_id:
            content["key_management"] = "customer_managed"
            content["kms_key_id"] = kms_key_id
        else:
            content["key_management"] = "aws_managed"
        controls = ["SC-28", "SC-28(1)"]
    else:
        content["encryption_state"] = "absent"
        content["gap"] = "encrypted not set to true"
        controls = ["SC-28"]

    return Evidence.create(
        detector_id="aws.encryption_ebs",
        ksis_evidenced=[],
        controls_evidenced=controls,
        source_ref=source_ref,
        content=content,
        timestamp=now,
    )


def _coerce_block_list(value: Any) -> list[dict[str, Any]]:
    """python-hcl2 emits single-block contents as a list of dicts; multiple
    blocks as a list of lists-of-dicts at various nesting depths. Normalize.
    """
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        out: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                out.append(item)
            elif isinstance(item, list):
                out.extend(x for x in item if isinstance(x, dict))
        return out
    return []
