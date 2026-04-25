"""Fixture-driven tests for `aws.sns_topic_encryption`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.sns_topic_encryption.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "sns_topic_encryption"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_cmk_referenced_emits_customer_managed_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "cmk_topic.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.sns_topic_encryption"
    assert ev.ksis_evidenced == []  # SC-28 has no FRMR KSI mapping; precedent.
    assert "SC-28" in ev.controls_evidenced
    assert ev.content["encryption_state"] == "customer_managed"
    assert "kms" in ev.content["kms_master_key_id"]


def test_topic_without_kms_attribute_emits_aws_managed_default() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "aws_managed_topic.tf")
    assert len(results) == 1
    assert results[0].content["encryption_state"] == "aws_managed_default"
    assert results[0].content["kms_master_key_id"] is None


def test_aws_managed_alias_emits_aws_managed_default() -> None:
    """`alias/aws/sns` is the AWS-managed key alias."""
    resource = TerraformResource(
        type="aws_sns_topic",
        name="aws_alias",
        body={"name": "x", "kms_master_key_id": "alias/aws/sns"},
        source_ref=SourceRef(file=Path("sns.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["encryption_state"] == "aws_managed_default"


def test_non_sns_resource_ignored() -> None:
    resource = TerraformResource(
        type="aws_sqs_queue",
        name="q",
        body={"kms_master_key_id": "alias/aws/sqs"},
        source_ref=SourceRef(file=Path("sqs.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []
