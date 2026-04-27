"""Fixture-driven tests for `aws.iam_managed_via_terraform`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.iam_managed_via_terraform.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "iam_managed_via_terraform"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ----------------------------------------------------------


def test_multi_iam_workspace_emits_one_summary_evidence() -> None:
    """Codebase with multiple IAM resource kinds → one summary evidence with
    counts broken down by short-form kind name."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "multi_iam.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.iam_managed_via_terraform"
    assert ev.ksis_evidenced == ["KSI-IAM-AAM"]
    assert ev.controls_evidenced == ["AC-2(2)"]
    content = ev.content
    assert content["resource_type"] == "iam_managed_via_terraform"
    assert content["resource_name"] == "(workspace)"
    assert content["automation_state"] == "tracked"
    # 2 roles + 1 policy + 1 user + 1 attachment = 5 IAM resources.
    assert content["iam_resource_count"] == 5
    assert content["distinct_iam_kinds"] == 4
    by_kind = content["by_kind"]
    assert by_kind["role"] == 2
    assert by_kind["policy"] == 1
    assert by_kind["user"] == 1
    assert by_kind["role_policy_attachment"] == 1


# --- should_not_match ------------------------------------------------------


def test_no_iam_resources_emits_nothing() -> None:
    """A codebase with no `aws_iam_*` resources produces no evidence — the
    Gap Agent classifies KSI-IAM-AAM accordingly."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "no_iam.tf")
    assert results == []


def test_empty_resource_list() -> None:
    assert detect([]) == []


# --- mapping metadata ------------------------------------------------------


def test_detector_registration_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.iam_managed_via_terraform"]
    assert spec.ksis == ("KSI-IAM-AAM",)
    assert spec.controls == ("AC-2(2)",)
    assert spec.source == "terraform"
