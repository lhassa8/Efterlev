"""Terraform-as-inventory detector.

Aggregates the scanned codebase's resources into a configuration-managed
inventory summary. KSI-PIY-GIV ("Generating Inventories") asks the customer
to "use authoritative sources to automatically generate real-time inventories
of all information resources." A Terraform codebase IS such an inventory —
every `resource "aws_*"` declaration is one tracked component, and the
state file (updated automatically on `terraform apply`) is the real-time
record of declared infrastructure.

This is a "meta" detector: rather than emitting one Evidence per resource
finding, it emits ONE summary Evidence per scan describing the inventory
posture as a whole. Down stream, the gap report shows a single inventory
card; the Gap Agent classifies KSI-PIY-GIV as `partial` or `implemented`
based on the inventory's size and breadth.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-PIY-GIV lists `cm-2.2`, `cm-7.5`, `cm-8`, `cm-8.1`, `cm-12`,
    `cm-12.1`, `cp-2.8` in its `controls` array. The inventory summary
    evidences CM-8 (System Component Inventory) directly and CM-8(1)
    (Updates During Installation/Removal — automated update on
    `terraform apply`). Other controls in the family are adjacent and
    remain candidates for future repo-metadata detectors (e.g.
    `dependabot.yml` evidencing CM-7.5, automated software allow-list).
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, SourceRef, TerraformResource


@detector(
    id="aws.terraform_inventory",
    ksis=["KSI-PIY-GIV"],
    controls=["CM-8", "CM-8(1)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one summary Evidence describing the codebase's resource inventory.

    Evidences (800-53):  CM-8 (System Component Inventory — the codebase
                         declares N resources, providing the authoritative
                         component list), CM-8(1) (Updates During
                         Installation/Removal — `terraform apply` updates
                         the state automatically; the IaC declaration is
                         the source of truth that drives those updates).
    Evidences (KSI):     KSI-PIY-GIV (Generating Inventories).
    Does NOT prove:      that runtime state matches the declaration (drift
                         detection is a separate concern; v1.5+ live-state
                         correlation), that the inventory is complete (the
                         scan only sees what's in this repo — multi-repo
                         deployments may distribute infrastructure across
                         many Terraform projects), or that the inventory
                         is reviewed at the cadence FedRAMP requires.
    """
    if not resources:
        return []

    type_counts: Counter[str] = Counter(r.type for r in resources)
    total = sum(type_counts.values())
    distinct_types = len(type_counts)

    # Top types by count, sorted by count descending then name ascending for
    # determinism. Cap at 10 to keep evidence content tight; larger codebases
    # rarely need more than the top-10 to characterize their inventory shape.
    top_types: list[dict[str, Any]] = [
        {"resource_type": t, "count": c}
        for t, c in sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    ]

    # Source ref: anchor at the first declared resource's file so the
    # Evidence has a real on-disk anchor for the provenance walker. The
    # inventory itself is workspace-scoped, but the walker needs SOMETHING
    # that resolves; using the first resource is pragmatic.
    first_ref = resources[0].source_ref
    summary_ref = SourceRef(file=Path(first_ref.file))

    content: dict[str, Any] = {
        "resource_type": "terraform_inventory",
        "resource_name": "(workspace)",
        "inventory_state": "tracked",
        "total_resources": total,
        "distinct_resource_types": distinct_types,
        "top_resource_types": top_types,
    }

    return [
        Evidence.create(
            detector_id="aws.terraform_inventory",
            ksis_evidenced=["KSI-PIY-GIV"],
            controls_evidenced=["CM-8", "CM-8(1)"],
            source_ref=summary_ref,
            content=content,
            timestamp=datetime.now(UTC),
        )
    ]
