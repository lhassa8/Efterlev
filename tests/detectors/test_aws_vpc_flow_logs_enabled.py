"""Fixture-driven tests for `aws.vpc_flow_logs_enabled`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.vpc_flow_logs_enabled.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "vpc_flow_logs_enabled"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ------------------------------------------------------------


def test_vpc_all_traffic_to_s3_records_target_and_destination() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_match" / "vpc_all_traffic_s3.tf"
    )
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.vpc_flow_logs_enabled"
    assert ev.ksis_evidenced == ["KSI-MLA-LET"]
    assert set(ev.controls_evidenced) == {"AU-2", "AU-12"}
    assert ev.content["target_kind"] == "vpc"
    assert ev.content["traffic_type"] == "ALL"
    assert ev.content["destination_type"] == "s3"


def test_subnet_reject_defaults_destination_to_cloudwatch_logs() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_match" / "subnet_reject_cwl.tf"
    )
    assert len(results) == 1
    ev = results[0]
    assert ev.content["target_kind"] == "subnet"
    assert ev.content["traffic_type"] == "REJECT"
    # destination_type omitted in HCL → detector defaults to cloud-watch-logs
    # (AWS's own default when log_destination_type is absent).
    assert ev.content["destination_type"] == "cloud-watch-logs"


# --- should_not_match --------------------------------------------------------


def test_no_flow_logs_emits_nothing() -> None:
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "no_flow_logs.tf"
    )
    assert results == []


# --- mapping metadata --------------------------------------------------------


def test_detector_registration_reflects_mla_let_and_au_2_au_12() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.vpc_flow_logs_enabled"]
    assert spec.ksis == ("KSI-MLA-LET",)
    assert "AU-2" in spec.controls
    assert "AU-12" in spec.controls
    assert spec.source == "terraform"
