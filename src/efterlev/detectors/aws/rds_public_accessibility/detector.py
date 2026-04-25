"""RDS public-accessibility detector.

Flags `aws_db_instance` / `aws_rds_cluster` / `aws_rds_cluster_instance`
resources with `publicly_accessible = true`. Per AWS docs, this attribute
controls whether the resource gets a public-internet-resolvable DNS name;
combined with permissive security groups, it's the canonical
"data plane on the public internet" misconfiguration.

The default is `false` — Terraform omitting the attribute means private,
which is the safe path. We only emit findings on the explicit-true case.
`(known after apply)` plan-JSON values are treated as unparseable.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-CNA-RNT (Restricting Network Traffic) — sc-7.5 mapping.
  - KSI-CNA-MAT (Minimizing Attack Surface) — broader sc-7 family.
Both clean.
"""

from __future__ import annotations

from datetime import UTC, datetime

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_RDS_TYPES = ("aws_db_instance", "aws_rds_cluster", "aws_rds_cluster_instance")


@detector(
    id="aws.rds_public_accessibility",
    ksis=["KSI-CNA-RNT", "KSI-CNA-MAT"],
    controls=["AC-3", "SC-7"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence for each RDS resource with public accessibility set true.

    Evidences (800-53):  AC-3 (Access Enforcement), SC-7 (Boundary Protection).
    Evidences (KSI):     KSI-CNA-RNT, KSI-CNA-MAT.
    Does NOT prove:      that the security groups attached to the RDS
                         allow internet ingress; that data ever crosses
                         the boundary even if access is granted; that
                         credentials enforce strong auth.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type not in _RDS_TYPES:
            continue
        ev = _classify(r, now)
        if ev is not None:
            out.append(ev)

    return out


def _classify(r: TerraformResource, now: datetime) -> Evidence | None:
    raw = r.body.get("publicly_accessible")

    # `(known after apply)` rendering from plan JSON or HCL interpolation
    # comes through as a string starting with `${` — unparseable, surface
    # as an unparseable-shape evidence record.
    if isinstance(raw, str) and raw.startswith("${"):
        return Evidence.create(
            detector_id="aws.rds_public_accessibility",
            ksis_evidenced=["KSI-CNA-RNT", "KSI-CNA-MAT"],
            controls_evidenced=["AC-3", "SC-7"],
            source_ref=r.source_ref,
            content={
                "resource_type": r.type,
                "resource_name": r.name,
                "exposure_state": "unparseable",
                "reason": "publicly_accessible value is unresolved (interpolation)",
            },
            timestamp=now,
        )

    if raw is True:
        return Evidence.create(
            detector_id="aws.rds_public_accessibility",
            ksis_evidenced=["KSI-CNA-RNT", "KSI-CNA-MAT"],
            controls_evidenced=["AC-3", "SC-7"],
            source_ref=r.source_ref,
            content={
                "resource_type": r.type,
                "resource_name": r.name,
                "exposure_state": "publicly_accessible",
                "gap": "publicly_accessible = true exposes the database to the public internet",
            },
            timestamp=now,
        )

    # `false` or absent → safe; no evidence emitted.
    return None
