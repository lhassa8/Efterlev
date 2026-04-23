"""Fixture-driven tests for `aws.encryption_ebs`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.encryption_ebs.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "encryption_ebs"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ------------------------------------------------------------


def test_standalone_encrypted_cmk_records_customer_managed() -> None:
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "standalone_cmk.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.encryption_ebs"
    assert ev.ksis_evidenced == []
    assert set(ev.controls_evidenced) == {"SC-28", "SC-28(1)"}
    assert ev.content["resource_type"] == "aws_ebs_volume"
    assert ev.content["location"] == "standalone"
    assert ev.content["encryption_state"] == "present"
    assert ev.content["key_management"] == "customer_managed"


def test_instance_root_block_device_encrypted() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_match" / "instance_encrypted_root.tf"
    )
    assert len(results) == 1
    ev = results[0]
    assert ev.content["resource_type"] == "aws_instance"
    assert ev.content["location"] == "root_block_device"
    assert ev.content["resource_name"] == "app.root_block_device"
    assert ev.content["encryption_state"] == "present"
    assert ev.content["key_management"] == "customer_managed"


# --- should_not_match --------------------------------------------------------


def test_standalone_unencrypted_emits_absent_with_gap() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "standalone_unencrypted.tf"
    )
    assert len(results) == 1
    ev = results[0]
    assert ev.content["encryption_state"] == "absent"
    assert ev.controls_evidenced == ["SC-28"]
    assert "gap" in ev.content


def test_instance_mixed_blocks_emits_per_block_records() -> None:
    # root_block_device encrypted; ebs_block_device NOT — detector emits
    # independent per-block Evidence so the Gap Agent sees both sides.
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "instance_plain_ebs_block.tf"
    )
    assert len(results) == 2
    by_loc = {ev.content["location"]: ev for ev in results}
    assert by_loc["root_block_device"].content["encryption_state"] == "present"
    assert by_loc["ebs_block_device"].content["encryption_state"] == "absent"
    assert "[0]" in by_loc["ebs_block_device"].content["resource_name"]


def test_no_ebs_resources_emits_nothing() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "no_ebs_resources.tf"
    )
    assert results == []


# --- mapping metadata --------------------------------------------------------


def test_detector_registration_reflects_empty_ksis_and_sc_28() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.encryption_ebs"]
    assert spec.ksis == ()
    assert "SC-28" in spec.controls
    assert "SC-28(1)" in spec.controls
    assert spec.source == "terraform"
