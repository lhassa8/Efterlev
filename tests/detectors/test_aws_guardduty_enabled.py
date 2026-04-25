"""Fixture-driven tests for `aws.guardduty_enabled`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.guardduty_enabled.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "guardduty_enabled"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_enabled_detector_emits_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "enabled_hourly.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.guardduty_enabled"
    assert ev.ksis_evidenced == ["KSI-MLA-OSM"]
    assert "SI-4" in ev.controls_evidenced
    assert ev.content["detector_state"] == "enabled"
    assert ev.content["finding_publishing_frequency"] == "ONE_HOUR"


def test_explicitly_disabled_emits_nothing() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "explicitly_disabled.tf")
    assert results == []


def test_enable_omitted_treated_as_enabled() -> None:
    """Terraform treats absent `enable` on guardduty_detector as enabled."""
    resource = TerraformResource(
        type="aws_guardduty_detector",
        name="default",
        body={},
        source_ref=SourceRef(file=Path("gd.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["detector_state"] == "enabled"


def test_non_guardduty_resource_ignored() -> None:
    resource = TerraformResource(
        type="aws_s3_bucket",
        name="b",
        body={"enable": True},
        source_ref=SourceRef(file=Path("s3.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []
