"""Fixture-driven tests for `aws.sqs_queue_encryption`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.sqs_queue_encryption.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "sqs_queue_encryption"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_cmk_referenced_emits_customer_managed_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "cmk_queue.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.sqs_queue_encryption"
    assert ev.ksis_evidenced == []  # SC-28 unmapped
    assert "SC-28" in ev.controls_evidenced
    assert ev.content["encryption_state"] == "customer_managed"


def test_unencrypted_queue_emits_absent_evidence_with_gap() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "no_encryption.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["encryption_state"] == "absent"
    assert "not encrypted at rest" in ev.content["gap"]


def test_aws_managed_alias_emits_aws_managed_default() -> None:
    resource = TerraformResource(
        type="aws_sqs_queue",
        name="aws_alias_queue",
        body={"name": "x", "kms_master_key_id": "alias/aws/sqs"},
        source_ref=SourceRef(file=Path("sqs.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["encryption_state"] == "aws_managed_default"


def test_sqs_managed_sse_enabled_emits_sqs_managed_state() -> None:
    resource = TerraformResource(
        type="aws_sqs_queue",
        name="sqs_managed",
        body={"name": "x", "sqs_managed_sse_enabled": True},
        source_ref=SourceRef(file=Path("sqs.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["encryption_state"] == "sqs_managed_sse"


def test_non_sqs_resource_ignored() -> None:
    resource = TerraformResource(
        type="aws_sns_topic",
        name="t",
        body={"kms_master_key_id": "alias/aws/sns"},
        source_ref=SourceRef(file=Path("sns.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []
