"""Fixture-driven tests for `github.immutable_deploy_patterns`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.github.immutable_deploy_patterns.detector import detect
from efterlev.github_workflows import parse_workflow_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "github"
    / "immutable_deploy_patterns"
)


def _run_detector_on(path: Path) -> list:
    workflow = parse_workflow_file(path)
    return detect([workflow])


# --- should_match ----------------------------------------------------------


def test_declarative_deploy_workflow_emits_present() -> None:
    """Workflow with terraform apply + helm upgrade. Both detected via run-step
    substring + uses-action prefix matching."""
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_match" / "declarative_deploy.yml"
    )
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "github.immutable_deploy_patterns"
    assert ev.ksis_evidenced == ["KSI-CMT-RMV"]
    assert set(ev.controls_evidenced) == {"CM-2", "CM-7"}
    content = ev.content
    assert content["resource_name"] == "Deploy"
    assert content["redeploy_pattern_state"] == "present"
    tools = set(content["declarative_tools_detected"])
    assert "terraform apply" in tools
    assert "helm upgrade" in tools
    assert "terraform" in tools  # from setup-terraform action
    assert "gap" not in content


# --- should_not_match ------------------------------------------------------


def test_lint_only_workflow_emits_absent_with_gap() -> None:
    """A lint-only workflow runs `terraform validate` (validation-shaped, NOT
    deploy-shaped). The detector should not match — `terraform validate` is
    not in the declarative-deploy substring list."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "lint_only.yml")
    assert len(results) == 1
    ev = results[0]
    content = ev.content
    assert content["redeploy_pattern_state"] == "absent"
    assert content["declarative_tools_detected"] == []
    assert "no declarative-deploy step" in content["gap"]


def test_no_workflows_emits_nothing() -> None:
    assert detect([]) == []


# --- mapping metadata ------------------------------------------------------


def test_detector_registration_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["github.immutable_deploy_patterns"]
    assert spec.ksis == ("KSI-CMT-RMV",)
    assert "CM-2" in spec.controls
    assert "CM-7" in spec.controls
    assert spec.source == "github-workflows"
