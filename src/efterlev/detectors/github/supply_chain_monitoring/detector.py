"""Supply-chain-monitoring detector.

Looks at every `.github/workflows/*.yml` workflow and reports whether
it runs SBOM-generation or upstream-vulnerability-scanning tooling.
KSI-SCR-MON ("Monitoring Supply Chain Risk") asks the customer to
"automatically monitor third party software information resources for
upstream vulnerabilities" — running `syft` to emit an SBOM and `grype`
or `trivy` to scan it for known CVEs is the canonical IaC-evidenceable
signal.

Sibling to `github.ci_validation_gates` (Priority 1.2). Both detectors
read the same `WorkflowFile` records produced by `parse_workflow_tree`;
this one looks for a different family of tools and evidences a
different KSI.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-SCR-MON lists `ra-5` (Vulnerability Monitoring and Scanning) and
    `sr-8` (Notification Agreements), among others. Tooling detected
    in CI evidences RA-5 directly. SR-8 (notification posture) is
    procedural and outside what a CI scan can verify.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.github_workflows import WorkflowFile
from efterlev.models import Evidence

# SBOM-generation tooling. Detected in step `run:` substrings.
_SBOM_TOOLS: tuple[str, ...] = (
    "syft",  # Anchore SBOM generator (the canonical OSS choice)
    "cyclonedx",  # cyclonedx-cli or language-specific cyclonedx-* tools
)

# Vulnerability-scanning tooling. Detected in step `run:` substrings.
# Per-language ecosystem audits (`pip-audit`, `npm audit`, `cargo audit`)
# count too — they cover the dependency tree the project actually uses.
_CVE_SCAN_TOOLS: tuple[str, ...] = (
    "grype",
    "trivy fs",  # filesystem mode — image mode is `trivy image`
    "trivy image",
    "snyk test",
    "snyk monitor",
    "pip-audit",
    "npm audit",
    "yarn audit",
    "cargo audit",
    "osv-scanner",
)

# Action-shaped tooling. Detected in step `uses:` substrings (action names).
# Map back to canonical tool names for a uniform evidence shape.
_ACTION_TOOL_MAP: dict[str, str] = {
    "anchore/syft-action": "syft",
    "anchore/scan-action": "grype",
    "aquasecurity/trivy-action": "trivy",
    "snyk/actions": "snyk",
    "ossf/scorecard-action": "ossf-scorecard",
    "actions/dependency-review-action": "github-dependency-review",
    "github/codeql-action": "codeql",
}


@detector(
    id="github.supply_chain_monitoring",
    ksis=["KSI-SCR-MON"],
    controls=["RA-5"],
    source="github-workflows",
    version="0.1.0",
)
def detect(workflows: list[WorkflowFile]) -> list[Evidence]:
    """Emit one Evidence per workflow, characterizing its supply-chain monitoring posture.

    Evidences (800-53):  RA-5 (Vulnerability Monitoring and Scanning).
    Evidences (KSI):     KSI-SCR-MON (Monitoring Supply Chain Risk).
    Does NOT prove:      that the scan step actually fails the build on
                         a finding (just that the tool runs); that the
                         scanner's signature database is current; that
                         findings are reviewed and acted on; or that
                         the workflow is wired into branch protection
                         required-checks.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for wf in workflows:
        out.append(_emit_workflow_evidence(wf, now))

    return out


def _emit_workflow_evidence(wf: WorkflowFile, now: datetime) -> Evidence:
    """Build one Evidence record characterizing a workflow's supply-chain posture."""
    sbom_tools, cve_tools = _detect_supply_chain_tools(wf)

    monitoring_state = "present" if sbom_tools or cve_tools else "absent"

    content: dict[str, Any] = {
        "resource_type": "github_workflow",
        "resource_name": wf.name,
        "sbom_tools_detected": list(sbom_tools),
        "cve_scan_tools_detected": list(cve_tools),
        "monitoring_state": monitoring_state,
    }

    if monitoring_state == "absent":
        content["gap"] = (
            f"Workflow `{wf.name}` runs but contains no SBOM-generation or "
            "upstream-vulnerability-scanning step. KSI-SCR-MON asks for "
            "automated monitoring of third-party software for upstream "
            "vulnerabilities; canonical evidence is SBOM (e.g. syft) and a "
            "CVE scanner (e.g. grype, trivy, snyk, pip-audit) running in CI."
        )

    return Evidence.create(
        detector_id="github.supply_chain_monitoring",
        ksis_evidenced=["KSI-SCR-MON"],
        controls_evidenced=["RA-5"],
        source_ref=wf.source_ref,
        content=content,
        timestamp=now,
    )


def _detect_supply_chain_tools(wf: WorkflowFile) -> tuple[list[str], list[str]]:
    """Return (sbom_tools, cve_scan_tools) detected in this workflow's steps.

    Walks every job's steps. Looks at both `run:` (shell commands) and
    `uses:` (action references). Action references map to canonical tool
    names via `_ACTION_TOOL_MAP`. Tools are deduplicated and sorted for
    deterministic output.
    """
    sbom: set[str] = set()
    cve: set[str] = set()

    for _job_name, job in wf.jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            run_cmd = step.get("run")
            if isinstance(run_cmd, str):
                for tool in _SBOM_TOOLS:
                    if tool in run_cmd:
                        sbom.add(tool)
                for tool in _CVE_SCAN_TOOLS:
                    if tool in run_cmd:
                        cve.add(tool)
            uses = step.get("uses")
            if isinstance(uses, str):
                # Match against the action prefix (before the @version tag).
                action_name = uses.split("@", 1)[0]
                for action_prefix, canonical in _ACTION_TOOL_MAP.items():
                    if action_name.startswith(action_prefix):
                        # Heuristic: actions that produce SBOMs go in the
                        # SBOM bucket; everything else is CVE-scanning or
                        # adjacent monitoring.
                        if canonical == "syft":
                            sbom.add(canonical)
                        else:
                            cve.add(canonical)
    return sorted(sbom), sorted(cve)
