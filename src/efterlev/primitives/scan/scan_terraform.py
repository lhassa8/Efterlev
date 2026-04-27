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
from typing import Literal

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


class ParseFailureRecord(BaseModel):
    """One file the parser couldn't read, surfaced through the scan output."""

    model_config = ConfigDict(frozen=True)

    file: Path
    reason: str


class ScanTerraformOutput(BaseModel):
    """Structured summary of a scan, with record IDs walkable via `provenance show`.

    `parse_failures` carries any .tf files the parser couldn't read. The scan
    is partial-success by design (per `parse_terraform_tree` collect-and-
    continue contract): one weird file should not block detection on the
    other 1800. Callers decide whether a partial-success scan is acceptable
    based on `parse_failures` and `resources_parsed`.
    """

    model_config = ConfigDict(frozen=True)

    resources_parsed: int
    detectors_run: int
    # Which scan mode produced this output. `hcl` parses .tf files directly
    # (this primitive); `plan` reads `terraform show -json` output (see
    # `scan_terraform_plan`). Surfaced to downstream agents so their narratives
    # can reflect coverage limitations when HCL mode hits a module-composed
    # codebase. Priority 0 (2026-04-27).
    scan_mode: Literal["hcl", "plan"] = "hcl"
    # Count of `module "<name>" {}` declarations the parser saw across the
    # tree. Detectors look at root-level `resource "aws_*"` declarations only;
    # resources defined inside upstream modules (the dominant ICP-A pattern)
    # are invisible to HCL-mode scans. The CLI uses this count to surface a
    # plan-JSON-recommended warning when a codebase is module-heavy. Priority 0.
    module_calls: int = 0
    evidence: list[Evidence] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    per_detector: list[DetectorRunSummary] = Field(default_factory=list)
    parse_failures: list[ParseFailureRecord] = Field(default_factory=list)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def files_failed(self) -> int:
        return len(self.parse_failures)

    @property
    def should_recommend_plan_json(self) -> bool:
        """True when the codebase is module-composed enough that HCL-mode
        coverage is meaningfully limited. Threshold derived from the
        2026-04-27 dogfood pass: that target had 11 module calls and 9
        resources, returned 1 evidence record. The threshold catches both
        "module-heavier than resource-heavier" and "any non-trivial use of
        modules" — a codebase with 3+ module calls is already at risk of
        having the bulk of its real workload invisible without plan-JSON.
        """
        return self.module_calls > self.resources_parsed or self.module_calls >= 3


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
    parse_result = parse_terraform_tree(input.target_dir)
    resources = parse_result.resources
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
        module_calls=parse_result.module_call_count,
        evidence=evidence,
        evidence_record_ids=evidence_record_ids,
        per_detector=per_detector,
        parse_failures=[
            ParseFailureRecord(file=f.file, reason=f.reason) for f in parse_result.parse_failures
        ],
    )
