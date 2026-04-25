"""AWS Config detector.

Emits Evidence when both `aws_config_configuration_recorder` AND
`aws_config_delivery_channel` resources are declared in the Terraform.
AWS Config needs both to actually record anything — a recorder without
a delivery channel is inert, and vice versa.

The detector also notes whether the recorder covers all-supported
resource types vs a custom subset (the former is stronger evidence).

KSI mapping per FRMR 0.9.43-beta:
  - KSI-MLA-EVC (Evaluating Configurations) — cm-2 is listed.
  - KSI-SVC-ACM (Automating Configuration Management) — cm-2 is listed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.config_enabled",
    ksis=["KSI-MLA-EVC", "KSI-SVC-ACM"],
    controls=["CM-2", "CM-8(2)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence when recorder + delivery channel are both declared.

    Evidences (800-53):  CM-2 (Baseline Configuration),
                         CM-8(2) (Automated Maintenance).
    Evidences (KSI):     KSI-MLA-EVC (Evaluating Configurations),
                         KSI-SVC-ACM (Automating Configuration Management).
    Does NOT prove:      that recorded changes are reviewed; that any
                         Config rules evaluate compliance; that the
                         delivery-channel S3 bucket is itself secure.
    """
    recorders: list[TerraformResource] = [
        r for r in resources if r.type == "aws_config_configuration_recorder"
    ]
    channels: list[TerraformResource] = [
        r for r in resources if r.type == "aws_config_delivery_channel"
    ]

    if not recorders or not channels:
        return []

    now = datetime.now(UTC)
    out: list[Evidence] = []

    # Emit one Evidence per recorder. Each pairs with the set of channels.
    for rec in recorders:
        out.append(_emit_recorder_evidence(rec, channels, now))

    return out


def _emit_recorder_evidence(
    recorder: TerraformResource,
    channels: list[TerraformResource],
    now: datetime,
) -> Evidence:
    recording_group = recorder.get_nested("recording_group")
    all_supported = _coerce_bool(
        recording_group.get("all_supported") if isinstance(recording_group, dict) else None
    )
    include_global = _coerce_bool(
        recording_group.get("include_global_resource_types")
        if isinstance(recording_group, dict)
        else None
    )

    if all_supported is True:
        coverage = "all_supported"
    elif all_supported is False:
        coverage = "custom_subset"
    else:
        coverage = "default"  # Attribute absent — AWS default is all_supported=true

    return Evidence.create(
        detector_id="aws.config_enabled",
        ksis_evidenced=["KSI-MLA-EVC", "KSI-SVC-ACM"],
        controls_evidenced=["CM-2", "CM-8(2)"],
        source_ref=recorder.source_ref,
        content={
            "resource_type": "aws_config_configuration_recorder",
            "resource_name": recorder.name,
            "recorder_state": "recording",
            "coverage": coverage,
            "include_global_resource_types": include_global,
            "delivery_channel_count": len(channels),
        },
        timestamp=now,
    )


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None
