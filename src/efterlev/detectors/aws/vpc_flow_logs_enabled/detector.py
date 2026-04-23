"""VPC flow-logs detector.

Scans `aws_flow_log` resources. Each records that network-layer logging
is declared for a given target (VPC, subnet, or ENI) — the complement to
CloudTrail's API-layer logging. Evidence records the target kind, the
traffic-type filter, and the destination type so the Gap Agent can
reason about coverage (e.g., "only REJECT traffic logged" is thinner
evidence than "ALL").

The detector intentionally does NOT emit negative evidence for VPCs that
lack flow logs — discovering which VPCs are uncovered requires seeing
`aws_vpc` resources too and cross-referencing. That cross-reference is
Gap Agent territory, mirroring the bucket↔public-access-block pattern.

FRMR 0.9.43-beta lists au-2 and au-12 in KSI-MLA-LET's controls array.
Clean mapping — we claim it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.vpc_flow_logs_enabled",
    ksis=["KSI-MLA-LET"],
    controls=["AU-2", "AU-12"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit flow-logs Evidence for every aws_flow_log found.

    Evidences (800-53):  AU-2 (Event Logging), AU-12 (Audit Record
                         Generation) — at the network layer.
    Evidences (KSI):     KSI-MLA-LET (Logging Event Types).
    Does NOT prove:      coverage — the detector does not check whether
                         every VPC has a flow log, only that declared
                         flow logs exist; log retention policy on the
                         destination bucket / log group; whether the
                         destination is itself secured; or runtime state.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_flow_log":
            continue
        out.append(_emit_flow_log_evidence(r, now))
    return out


def _emit_flow_log_evidence(r: TerraformResource, now: datetime) -> Evidence:
    body = r.body

    target_kind, target_ref = _identify_target(body)
    traffic_type = body.get("traffic_type") or "ALL"  # AWS defaults to ALL
    destination_type = body.get("log_destination_type") or "cloud-watch-logs"

    content: dict[str, Any] = {
        "resource_type": r.type,
        "resource_name": r.name,
        "target_kind": target_kind,
        "traffic_type": traffic_type,
        "destination_type": destination_type,
    }
    if target_ref is not None:
        content["target_ref"] = target_ref

    return Evidence.create(
        detector_id="aws.vpc_flow_logs_enabled",
        ksis_evidenced=["KSI-MLA-LET"],
        controls_evidenced=["AU-2", "AU-12"],
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )


def _identify_target(body: dict[str, Any]) -> tuple[str, str | None]:
    """Return (kind, ref) naming which attachment target the flow log covers.

    Exactly one of vpc_id / subnet_id / eni_id is valid per flow log, but
    HCL doesn't enforce that at parse time. We pick the most-specific one
    set; unknown means the Terraform is malformed (we record kind=unknown
    rather than raising).
    """
    for field, kind in (("eni_id", "eni"), ("subnet_id", "subnet"), ("vpc_id", "vpc")):
        val = body.get(field)
        if val:
            ref = val if isinstance(val, str) else None
            return kind, ref
    return "unknown", None
