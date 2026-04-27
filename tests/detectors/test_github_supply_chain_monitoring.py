"""Fixture-driven tests for `github.supply_chain_monitoring`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.github.supply_chain_monitoring.detector import detect
from efterlev.github_workflows import parse_workflow_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "github"
    / "supply_chain_monitoring"
)


def _run_detector_on(path: Path) -> list:
    workflow = parse_workflow_file(path)
    return detect([workflow])


# --- should_match ----------------------------------------------------------


def test_sbom_and_scan_workflow_emits_present_with_tools() -> None:
    """A workflow that runs SBOM generation + multiple scanners. Both bucket
    lists populate; monitoring_state is present."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "sbom_and_scan.yml")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "github.supply_chain_monitoring"
    assert ev.ksis_evidenced == ["KSI-SCR-MON"]
    assert ev.controls_evidenced == ["RA-5"]
    content = ev.content
    assert content["resource_type"] == "github_workflow"
    assert content["resource_name"] == "Security"
    assert content["monitoring_state"] == "present"
    sbom = set(content["sbom_tools_detected"])
    cve = set(content["cve_scan_tools_detected"])
    assert "syft" in sbom
    assert "grype" in cve
    assert "pip-audit" in cve
    assert "ossf-scorecard" in cve
    assert "gap" not in content


# --- should_not_match ------------------------------------------------------


def test_lint_only_workflow_emits_absent_with_gap() -> None:
    """A lint-only workflow has no supply-chain tooling — emit absent +
    gap. The customer can read the gap field to know what would help."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "lint_only.yml")
    assert len(results) == 1
    ev = results[0]
    content = ev.content
    assert content["monitoring_state"] == "absent"
    assert content["sbom_tools_detected"] == []
    assert content["cve_scan_tools_detected"] == []
    assert "no SBOM-generation or upstream-vulnerability-scanning step" in content["gap"]


def test_no_workflows_emits_nothing() -> None:
    """An empty workflow list yields no evidence."""
    assert detect([]) == []


# --- mapping metadata ------------------------------------------------------


def test_detector_registration_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["github.supply_chain_monitoring"]
    assert spec.ksis == ("KSI-SCR-MON",)
    assert spec.controls == ("RA-5",)
    assert spec.source == "github-workflows"
