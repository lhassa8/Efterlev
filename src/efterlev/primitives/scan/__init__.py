"""Scan primitives — parse source material and run detectors.

Importing this package also imports the scan primitive modules below, which
trigger `@primitive` registration and (transitively) `@detector`
registration via `efterlev.detectors`.
"""

from __future__ import annotations

from efterlev.models import ScanSummary
from efterlev.primitives.scan.scan_terraform import (
    ScanTerraformInput,
    ScanTerraformOutput,
    scan_terraform,
)
from efterlev.primitives.scan.scan_terraform_plan import (
    ScanTerraformPlanInput,
    scan_terraform_plan,
)
from efterlev.provenance.store import ProvenanceStore


def latest_scan_summary(store: ProvenanceStore) -> ScanSummary | None:
    """Build a `ScanSummary` from the most recent scan-primitive invocation.

    Looks for either `scan_terraform@*` or `scan_terraform_plan@*` records;
    returns None when no scan has been run against this store. The payload is
    the `@primitive` decorator's `{"input": ..., "output": ...}` shape;
    `output` is a serialized `ScanTerraformOutput`.

    Used by the agent CLI commands (`efterlev agent gap` / `agent document`)
    to surface scan-quality metadata to the agent prompt — Priority 0
    (2026-04-27). When the most recent scan was an HCL-mode run against a
    module-composed codebase, the agent's narrative can reflect the coverage
    limitation rather than treating thin evidence as a real implementation
    gap.
    """
    # Try plan-mode first (typical for module-composed codebases) and fall
    # back to HCL — but actually take whichever was MORE RECENT, because a
    # user iterating "scan plan, then re-scan HCL after editing one file"
    # should see the latest run reflected. Achieved by querying both prefixes
    # and picking the newer record.
    plan_match = store.latest_record_with_primitive_prefix("scan_terraform_plan@")
    hcl_match = store.latest_record_with_primitive_prefix("scan_terraform@")

    candidates = [m for m in (plan_match, hcl_match) if m is not None]
    if not candidates:
        return None

    # Pick the newer record across both prefixes. The record itself isn't
    # needed beyond timestamp comparison — we extract from `payload`.
    _record, payload = max(candidates, key=lambda m: m[0].timestamp)

    output = payload.get("output")
    if not isinstance(output, dict):
        return None

    try:
        return ScanSummary(
            scan_mode=output.get("scan_mode", "hcl"),
            resources_parsed=int(output.get("resources_parsed", 0)),
            module_calls=int(output.get("module_calls", 0)),
            evidence_count=len(output.get("evidence", []) or []),
        )
    except (TypeError, ValueError):
        return None


__all__ = [
    "ScanSummary",
    "ScanTerraformInput",
    "ScanTerraformOutput",
    "ScanTerraformPlanInput",
    "latest_scan_summary",
    "scan_terraform",
    "scan_terraform_plan",
]
