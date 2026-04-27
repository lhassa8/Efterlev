"""ScanSummary — slim, agent-facing summary of what the most recent scan saw.

The full `ScanTerraformOutput` carries the evidence list, per-detector counts,
parse failures, and so on — too much detail to put in an agent's prompt without
crowding out the actual evidence. `ScanSummary` is the small, prompt-shaped
projection: what mode ran, what was parsed, what the user should know about
coverage.

Surfaced to Gap and Documentation agents (Priority 0, 2026-04-27) so their
narratives can reflect coverage limitations when an HCL-mode scan hit a
module-composed codebase. Without this, narratives say generic things like
"the scanner could in principle detect CloudTrail, Config, or audit log
resources from IaC, but none were observed" when the more accurate framing
is "this scan was HCL-mode against a codebase that composes upstream modules;
findings classified `not_implemented` may be coverage gaps rather than real
gaps."

Built by `latest_scan_summary()` in `efterlev.primitives.scan` from the most
recent scan-primitive invocation in the active store.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ScanSummary(BaseModel):
    """What the most recent scan produced — slim, agent-prompt-shaped."""

    model_config = ConfigDict(frozen=True)

    scan_mode: Literal["hcl", "plan"]
    """`hcl` parsed .tf files directly. `plan` read `terraform show -json` output."""

    resources_parsed: int
    """Count of root-level `resource` declarations the scan saw."""

    module_calls: int
    """Count of `module "<name>" {}` declarations. Always 0 in `plan` mode (modules
    are already expanded into resolved resources by `terraform show -json`)."""

    evidence_count: int
    """How many Evidence records the scan produced. A coverage proxy: a scan
    against a real codebase that produces 0-1 records is suspicious."""

    @property
    def recommend_plan_json(self) -> bool:
        """True when an HCL-mode scan hit a module-composed codebase. Mirrors
        the threshold in `ScanTerraformOutput.should_recommend_plan_json` but
        is computable from this slim summary alone (which is what agents
        receive). Plan-mode scans never trigger because `module_calls` is 0
        there by construction."""
        return self.scan_mode == "hcl" and (
            self.module_calls > self.resources_parsed or self.module_calls >= 3
        )
