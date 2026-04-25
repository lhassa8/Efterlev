"""Fixture-driven tests for `aws.rds_encryption_at_rest`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.rds_encryption_at_rest.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "rds_encryption_at_rest"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ------------------------------------------------------------


def test_encrypted_with_cmk_records_customer_managed() -> None:
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "encrypted_cmk.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.rds_encryption_at_rest"
    assert ev.ksis_evidenced == []
    assert set(ev.controls_evidenced) == {"SC-28", "SC-28(1)"}
    assert ev.content["encryption_state"] == "present"
    assert ev.content["algorithm"] == "AES256"
    assert ev.content["key_management"] == "customer_managed"
    assert ev.content["kms_key_id"].startswith("arn:aws:kms:")


def test_encrypted_without_cmk_records_aws_managed() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_match" / "encrypted_aws_managed.tf"
    )
    assert len(results) == 1
    ev = results[0]
    assert ev.content["encryption_state"] == "present"
    assert ev.content["key_management"] == "aws_managed"
    assert "kms_key_id" not in ev.content


# --- should_not_match --------------------------------------------------------


def test_unencrypted_rds_emits_absent_with_gap() -> None:
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "unencrypted.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["encryption_state"] == "absent"
    assert ev.controls_evidenced == ["SC-28"]
    assert "gap" in ev.content


def test_no_rds_resources_emits_nothing() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "no_rds_resources.tf"
    )
    assert results == []


# --- mapping metadata --------------------------------------------------------


def test_detector_registration_reflects_empty_ksis_and_sc_28() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.rds_encryption_at_rest"]
    assert spec.ksis == ()
    assert "SC-28" in spec.controls
    assert "SC-28(1)" in spec.controls
    assert spec.source == "terraform"
