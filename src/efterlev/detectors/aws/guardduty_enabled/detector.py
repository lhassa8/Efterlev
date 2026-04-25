"""GuardDuty detector.

Emits Evidence for `aws_guardduty_detector` resources with `enable = true`.
Explicit `enable = false` and resources without `enable` set are treated
as disabled (AWS default for the resource is enabled when declared, but
Terraform-declared-with-enable-false is an explicit opt-out).

KSI mapping per FRMR 0.9.43-beta:
  - KSI-MLA-OSM (Operating SIEM Capability) — SI-4 based.
"""

from __future__ import annotations

from datetime import UTC, datetime

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.guardduty_enabled",
    ksis=["KSI-MLA-OSM"],
    controls=["SI-4", "RA-5(11)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence for each enabled aws_guardduty_detector.

    Evidences (800-53):  SI-4 (Information System Monitoring),
                         RA-5(11) (Public Disclosure Program).
    Evidences (KSI):     KSI-MLA-OSM (Operating SIEM Capability).
    Does NOT prove:      that findings are routed to any human or
                         automated response; that the detector covers
                         all regions the workload spans; that cross-
                         account org-admin wiring is set up.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_guardduty_detector":
            continue
        enable = r.body.get("enable", True)  # AWS default is enable=true when declared
        if enable is not True:
            continue
        out.append(_emit_enabled(r, now))

    return out


def _emit_enabled(r: TerraformResource, now: datetime) -> Evidence:
    finding_freq = r.body.get("finding_publishing_frequency")
    return Evidence.create(
        detector_id="aws.guardduty_enabled",
        ksis_evidenced=["KSI-MLA-OSM"],
        controls_evidenced=["SI-4", "RA-5(11)"],
        source_ref=r.source_ref,
        content={
            "resource_type": "aws_guardduty_detector",
            "resource_name": r.name,
            "detector_state": "enabled",
            "finding_publishing_frequency": finding_freq if isinstance(finding_freq, str) else None,
        },
        timestamp=now,
    )
