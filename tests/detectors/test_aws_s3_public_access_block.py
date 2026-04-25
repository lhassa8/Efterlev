"""Fixture-driven tests for `aws.s3_public_access_block`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.s3_public_access_block.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "s3_public_access_block"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ------------------------------------------------------------


def test_all_flags_true_emits_fully_blocked() -> None:
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "all_flags_true.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.s3_public_access_block"
    assert ev.ksis_evidenced == []
    assert ev.controls_evidenced == ["AC-3"]
    assert ev.content["resource_type"] == "aws_s3_bucket_public_access_block"
    assert ev.content["resource_name"] == "reports"
    assert ev.content["posture"] == "fully_blocked"
    assert ev.content["flags"] == {
        "block_public_acls": True,
        "ignore_public_acls": True,
        "block_public_policy": True,
        "restrict_public_buckets": True,
    }
    assert "gap" not in ev.content


# --- should_not_match --------------------------------------------------------


def test_partial_flags_emits_partial_with_gap() -> None:
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "partial_flags.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["posture"] == "partial"
    assert ev.content["resource_name"] == "loose"
    # Two flags are explicitly false; "gap" names them.
    assert "block_public_policy" in ev.content["gap"]
    assert "restrict_public_buckets" in ev.content["gap"]


def test_no_pab_resources_emits_nothing() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "no_pab_resources.tf"
    )
    assert results == []


# --- mapping metadata --------------------------------------------------------


def test_detector_registration_reflects_empty_ksis_and_ac_3() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.s3_public_access_block"]
    assert spec.ksis == ()
    assert spec.controls == ("AC-3",)
    assert spec.source == "terraform"
