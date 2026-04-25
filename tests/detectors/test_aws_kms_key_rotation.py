"""Fixture-driven tests for `aws.kms_key_rotation`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.kms_key_rotation.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "kms_key_rotation"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ------------------------------------------------------------


def test_symmetric_rotated_emits_enabled() -> None:
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "symmetric_rotated.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.kms_key_rotation"
    assert ev.ksis_evidenced == []
    assert set(ev.controls_evidenced) == {"SC-12", "SC-12(2)"}
    assert ev.content["rotation_status"] == "enabled"
    assert "gap" not in ev.content


# --- should_not_match --------------------------------------------------------


def test_symmetric_unrotated_emits_disabled_with_gap() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "symmetric_unrotated.tf"
    )
    assert len(results) == 1
    ev = results[0]
    assert ev.content["rotation_status"] == "disabled"
    assert ev.controls_evidenced == ["SC-12"]  # no enhancement when disabled
    assert "gap" in ev.content


def test_asymmetric_key_emits_not_applicable() -> None:
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "asymmetric_key.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["rotation_status"] == "not_applicable"
    assert ev.content["key_spec"] == "RSA_4096"
    assert "note" in ev.content
    assert ev.controls_evidenced == ["SC-12"]


def test_no_kms_resources_emits_nothing() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "no_kms_resources.tf"
    )
    assert results == []


# --- mapping metadata --------------------------------------------------------


def test_detector_registration_reflects_empty_ksis_and_sc_12() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.kms_key_rotation"]
    assert spec.ksis == ()
    assert "SC-12" in spec.controls
    assert "SC-12(2)" in spec.controls
    assert spec.source == "terraform"
