"""`scan_terraform` primitive — parse a .tf tree, run every detector, persist Evidence.

This is the detector orchestrator. It does four things:

  1. Parse the target directory into `TerraformResource` records (delegated to
     `efterlev.terraform`).
  2. Iterate the detector registry, filter by `source="terraform"`, and call
     each detector with the parsed resources.
  3. Return a typed summary (ScanTerraformOutput). Evidence persistence to the
     active provenance store is handled by the `@detector` decorator itself,
     so this primitive doesn't manually touch the store.
  4. Also returns the evidence records so callers (CLI, agents) can print or
     reason over them without re-reading the store.

Detector discovery: importing `efterlev.detectors` at module top registers
every detector in the library. The scan primitive then enumerates
`efterlev.detectors.base.get_registry()` — a simple, explicit registry
rather than a pkgutil-style autodiscovery. Adding a detector is adding an
import line in `efterlev/detectors/__init__.py`.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

import efterlev.detectors  # noqa: F401 — triggers detector registrations
from efterlev.detectors.base import Source, get_registry
from efterlev.models import Evidence
from efterlev.primitives.base import primitive
from efterlev.provenance.context import get_active_store
from efterlev.terraform import parse_terraform_tree


class ScanTerraformInput(BaseModel):
    """Input to `scan_terraform`."""

    model_config = ConfigDict(frozen=True)

    target_dir: Path


class DetectorRunSummary(BaseModel):
    """One detector's contribution to a scan."""

    model_config = ConfigDict(frozen=True)

    detector_id: str
    version: str
    evidence_count: int


class ScanTerraformOutput(BaseModel):
    """Structured summary of a scan, with record IDs walkable via `provenance show`."""

    model_config = ConfigDict(frozen=True)

    resources_parsed: int
    detectors_run: int
    evidence: list[Evidence] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    per_detector: list[DetectorRunSummary] = Field(default_factory=list)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)


@primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
def scan_terraform(input: ScanTerraformInput) -> ScanTerraformOutput:
    """Parse the target .tf tree and run every Terraform-source detector over it.

    Each detector's `@detector` decorator persists its returned Evidence into
    the active store. We snapshot `iter_records()` before and after the
    detector loop to recover the store-side `record_id`s the user will pass
    to `efterlev provenance show` — `Evidence.evidence_id` is a separate
    content hash from `ProvenanceRecord.record_id`, so exposing the record
    IDs explicitly is clearer than making the CLI do the mapping.
    """
    resources = parse_terraform_tree(input.target_dir)
    terraform_source: Source = "terraform"
    terraform_detectors = [
        spec for spec in get_registry().values() if spec.source == terraform_source
    ]

    store = get_active_store()
    pre_ids: set[str] = set(store.iter_records()) if store is not None else set()

    evidence: list[Evidence] = []
    per_detector: list[DetectorRunSummary] = []
    for spec in terraform_detectors:
        produced = spec.callable(resources)
        evidence.extend(produced)
        per_detector.append(
            DetectorRunSummary(
                detector_id=spec.id,
                version=spec.version,
                evidence_count=len(produced),
            )
        )

    # Records written by detectors during this scan. The primitive's own
    # invocation record is written by the @primitive wrapper *after* this
    # function returns, so it's not in this set.
    evidence_record_ids: list[str] = []
    if store is not None:
        for rid in store.iter_records():
            if rid not in pre_ids:
                evidence_record_ids.append(rid)

    return ScanTerraformOutput(
        resources_parsed=len(resources),
        detectors_run=len(terraform_detectors),
        evidence=evidence,
        evidence_record_ids=evidence_record_ids,
        per_detector=per_detector,
    )
