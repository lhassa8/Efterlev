"""Fixture-driven tests for `github.action_pinning`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.github.action_pinning.detector import detect
from efterlev.github_workflows import parse_workflow_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "github"
    / "action_pinning"
)


def _run_detector_on(path: Path) -> list:
    workflow = parse_workflow_file(path)
    return detect([workflow])


# --- should_match ----------------------------------------------------------


def test_all_pinned_workflow_emits_all_pinned_state() -> None:
    """Workflow with every `uses:` ref pointing to a 40-char SHA. Detector
    classifies `pin_state="all_pinned"` and emits no gap."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "all_pinned.yml")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "github.action_pinning"
    assert ev.ksis_evidenced == ["KSI-SCR-MIT"]
    assert set(ev.controls_evidenced) == {"SR-5", "SI-7(1)"}
    content = ev.content
    assert content["resource_name"] == "Release"
    assert content["pin_state"] == "all_pinned"
    assert content["external_action_count"] == 4
    assert content["pinned_action_count"] == 4
    assert content["mutable_action_refs"] == []
    assert "gap" not in content


# --- should_not_match ------------------------------------------------------


def test_tag_refs_workflow_emits_none_pinned_with_gap() -> None:
    """Workflow with every `uses:` ref pointing to a tag/branch (mutable).
    Detector classifies `pin_state="none_pinned"` and emits a gap field
    enumerating the mutable refs."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "tag_refs.yml")
    assert len(results) == 1
    ev = results[0]
    content = ev.content
    assert content["pin_state"] == "none_pinned"
    assert content["external_action_count"] == 4
    assert content["pinned_action_count"] == 0
    refs = set(content["mutable_action_refs"])
    assert "actions/checkout@v4" in refs
    assert "codecov/codecov-action@main" in refs
    assert "gap" in content
    assert "compromised-tag" in content["gap"]


def test_no_workflows_emits_nothing() -> None:
    assert detect([]) == []


# --- pin-state classification edge cases ----------------------------------


def test_local_and_docker_refs_are_excluded_from_count() -> None:
    """Local refs (`./...`) and docker refs (`docker://...`) have different
    supply-chain semantics and aren't classified by this detector."""
    from efterlev.github_workflows import WorkflowFile
    from efterlev.models import SourceRef

    wf = WorkflowFile(
        name="local",
        jobs={
            "main": {
                "steps": [
                    {"uses": "./.github/local-action"},
                    {"uses": "docker://alpine:3"},
                    {"uses": "actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11"},
                ]
            }
        },
        source_ref=SourceRef(file=Path(".github/workflows/local.yml"), line_start=1, line_end=10),
    )
    results = detect([wf])
    assert len(results) == 1
    content = results[0].content
    # Local + docker refs are excluded; only the SHA-pinned action counts.
    assert content["external_action_count"] == 1
    assert content["pinned_action_count"] == 1
    assert content["pin_state"] == "all_pinned"


def test_mixed_workflow_emits_mixed_state() -> None:
    """Workflow with both pinned and mutable refs lands in `pin_state="mixed"`
    with a gap field listing only the mutable ones."""
    from efterlev.github_workflows import WorkflowFile
    from efterlev.models import SourceRef

    wf = WorkflowFile(
        name="mixed",
        jobs={
            "main": {
                "steps": [
                    {"uses": "actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11"},
                    {"uses": "actions/setup-python@v5"},
                ]
            }
        },
        source_ref=SourceRef(file=Path(".github/workflows/mixed.yml"), line_start=1, line_end=10),
    )
    results = detect([wf])
    assert len(results) == 1
    content = results[0].content
    assert content["pin_state"] == "mixed"
    assert content["external_action_count"] == 2
    assert content["pinned_action_count"] == 1
    assert content["mutable_action_refs"] == ["actions/setup-python@v5"]


def test_workflow_with_no_external_actions_emits_no_external_actions() -> None:
    """A workflow with only `run:` steps (no `uses:`) has no opinion on pin
    posture — `pin_state="no_external_actions"`."""
    from efterlev.github_workflows import WorkflowFile
    from efterlev.models import SourceRef

    wf = WorkflowFile(
        name="run_only",
        jobs={
            "main": {
                "steps": [
                    {"run": "echo hello"},
                    {"run": "make test"},
                ]
            }
        },
        source_ref=SourceRef(
            file=Path(".github/workflows/run_only.yml"), line_start=1, line_end=10
        ),
    )
    results = detect([wf])
    assert len(results) == 1
    content = results[0].content
    assert content["pin_state"] == "no_external_actions"
    assert content["external_action_count"] == 0
    assert "gap" not in content


# --- mapping metadata ------------------------------------------------------


def test_detector_registration_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["github.action_pinning"]
    assert spec.ksis == ("KSI-SCR-MIT",)
    assert "SR-5" in spec.controls
    assert "SI-7(1)" in spec.controls
    assert spec.source == "github-workflows"
