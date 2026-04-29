"""Fixture-driven tests for `aws.iam_user_access_keys`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.iam_user_access_keys.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "iam_user_access_keys"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ------------------------------------------------------------


def test_active_key_flags_gap() -> None:
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "ci_deploy_key.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.iam_user_access_keys"
    assert ev.ksis_evidenced == ["KSI-IAM-SNU", "KSI-IAM-MFA"]
    assert set(ev.controls_evidenced) == {"IA-2", "AC-2"}
    assert ev.content["resource_name"] == "ci_deploy"
    assert ev.content["status"] == "Active"
    assert ev.content["gap"]
    # User reference from aws_iam_user.X.name comes through as an HCL interp.
    assert ev.content["attached_user"] is not None


def test_inactive_key_still_flags_gap_with_pgp_wrapping() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_match" / "inactive_key_with_pgp.tf"
    )
    assert len(results) == 1
    ev = results[0]
    assert ev.content["status"] == "Inactive"  # still a declared key
    assert ev.content.get("secret_wrapping") == "pgp"
    assert ev.content["gap"]


# --- should_not_match --------------------------------------------------------


def test_role_and_user_without_keys_emits_nothing() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "role_only_no_keys.tf"
    )
    assert results == []


# --- mapping metadata --------------------------------------------------------


def test_detector_registration_reflects_iam_snu_primary_iam_mfa_crossmap() -> None:
    # Post-2026-04-29 audit (PR #90): KSI-IAM-SNU is the primary
    # mapping (long-lived programmatic access keys are the canonical
    # insecure non-user auth pattern); KSI-IAM-MFA is cross-mapped via
    # the MFA-bypass-via-access-key reasoning.
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.iam_user_access_keys"]
    assert spec.ksis == ("KSI-IAM-SNU", "KSI-IAM-MFA")
    assert "IA-2" in spec.controls
    assert "AC-2" in spec.controls
    assert spec.source == "terraform"
