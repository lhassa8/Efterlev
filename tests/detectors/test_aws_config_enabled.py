"""Fixture-driven tests for `aws.config_enabled`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.config_enabled.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "config_enabled"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_recorder_plus_channel_emits_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "recorder_and_channel.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.config_enabled"
    assert set(ev.ksis_evidenced) == {"KSI-MLA-EVC", "KSI-SVC-ACM"}
    assert "CM-2" in ev.controls_evidenced
    assert ev.content["coverage"] == "all_supported"
    assert ev.content["include_global_resource_types"] is True
    assert ev.content["delivery_channel_count"] == 1


def test_recorder_without_channel_emits_nothing() -> None:
    """Config is inert without a delivery channel."""
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "recorder_only.tf")
    assert results == []


def test_channel_without_recorder_emits_nothing() -> None:
    resource = TerraformResource(
        type="aws_config_delivery_channel",
        name="orphan_channel",
        body={"name": "x", "s3_bucket_name": "y"},
        source_ref=SourceRef(file=Path("chan.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []


def test_custom_subset_recorder_emits_custom_subset_coverage() -> None:
    recorder = TerraformResource(
        type="aws_config_configuration_recorder",
        name="subset",
        body={
            "name": "subset",
            "role_arn": "arn:aws:iam::123456789012:role/x",
            "recording_group": [
                {
                    "all_supported": False,
                    "resource_types": ["AWS::S3::Bucket", "AWS::IAM::User"],
                }
            ],
        },
        source_ref=SourceRef(file=Path("rec.tf"), line_start=1, line_end=10),
    )
    channel = TerraformResource(
        type="aws_config_delivery_channel",
        name="chan",
        body={"name": "chan", "s3_bucket_name": "bucket"},
        source_ref=SourceRef(file=Path("chan.tf"), line_start=1, line_end=5),
    )
    results = detect([recorder, channel])
    assert len(results) == 1
    assert results[0].content["coverage"] == "custom_subset"


def test_recorder_without_recording_group_emits_default_coverage() -> None:
    recorder = TerraformResource(
        type="aws_config_configuration_recorder",
        name="default",
        body={"name": "default", "role_arn": "arn:aws:iam::123456789012:role/x"},
        source_ref=SourceRef(file=Path("rec.tf"), line_start=1, line_end=5),
    )
    channel = TerraformResource(
        type="aws_config_delivery_channel",
        name="chan",
        body={"name": "chan", "s3_bucket_name": "bucket"},
        source_ref=SourceRef(file=Path("chan.tf"), line_start=1, line_end=5),
    )
    results = detect([recorder, channel])
    assert len(results) == 1
    assert results[0].content["coverage"] == "default"
