"""`scan_terraform_plan` primitive — parse a `terraform show -json` plan,
run every detector, persist Evidence.

Sibling to `scan_terraform` but takes a user-supplied plan JSON file
instead of a .tf tree. Per DECISIONS 2026-04-22 "Design: Terraform Plan
JSON support", the plan-JSON translator produces TerraformResource
objects shape-compatible with what the HCL parser emits, so existing
detectors (filtered by `source="terraform"`) run unchanged. Detectors
that opt into `source="terraform-plan"` specifically — reserved for
future detectors that need resolved values not present in HCL — also
run here.

The output shape reuses `ScanTerraformOutput` (no new type) because the
downstream CLI / agent / renderer consumers don't care whether Evidence
originated from HCL parse or plan translation — the Evidence records
themselves already identify their detector and carry their own
source_ref.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

import efterlev.detectors  # noqa: F401 — triggers detector registrations
from efterlev.detectors.base import Source, get_registry
from efterlev.models import Evidence
from efterlev.primitives.base import primitive
from efterlev.primitives.scan.scan_terraform import (
    DetectorRunSummary,
    ScanTerraformOutput,
)
from efterlev.provenance.context import get_active_store
from efterlev.terraform import parse_plan_json


class ScanTerraformPlanInput(BaseModel):
    """Input to `scan_terraform_plan`."""

    model_config = ConfigDict(frozen=True)

    plan_file: Path
    # When set, Evidence source_refs are written relative to this root —
    # matches the post-fixup-D repo-relative-path contract. Typically the
    # repo root of the scanned codebase.
    target_root: Path | None = None


@primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
def scan_terraform_plan(input: ScanTerraformPlanInput) -> ScanTerraformOutput:
    """Parse the plan JSON and run every terraform-source detector over it.

    Applicable detectors:
      - `source="terraform"` — the existing HCL-focused detectors, which
        work against plan-translated TerraformResources unchanged per
        design call #3.
      - `source="terraform-plan"` — reserved slot for future detectors
        that require resolved values. None exist yet, but the filter
        admits them so the registry extension point works on day one.

    Evidence persistence is handled by the `@detector` decorator against
    the active provenance store, same as `scan_terraform`.
    """
    resources = parse_plan_json(input.plan_file, target_root=input.target_root)

    applicable_sources: set[Source] = {"terraform", "terraform-plan"}
    detectors = [spec for spec in get_registry().values() if spec.source in applicable_sources]

    store = get_active_store()
    pre_ids: set[str] = set(store.iter_records()) if store is not None else set()

    evidence: list[Evidence] = []
    per_detector: list[DetectorRunSummary] = []
    for spec in detectors:
        produced = spec.callable(resources)
        evidence.extend(produced)
        per_detector.append(
            DetectorRunSummary(
                detector_id=spec.id,
                version=spec.version,
                evidence_count=len(produced),
            )
        )

    evidence_record_ids: list[str] = []
    if store is not None:
        evidence_record_ids = [rid for rid in store.iter_records() if rid not in pre_ids]

    return ScanTerraformOutput(
        resources_parsed=len(resources),
        detectors_run=len(detectors),
        scan_mode="plan",
        evidence=evidence,
        evidence_record_ids=evidence_record_ids,
        per_detector=per_detector,
    )
