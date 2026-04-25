"""Fixture-driven tests for `aws.secrets_manager_rotation`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.secrets_manager_rotation.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "secrets_manager_rotation"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_paired_secret_and_rotation_within_window_emits_positive_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "db_password_30_day.tf")
    # Only the rotation evidence should fire (the secret is paired by name).
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.secrets_manager_rotation"
    assert set(ev.ksis_evidenced) == {"KSI-SVC-ASM", "KSI-IAM-SNU"}
    assert "SC-12" in ev.controls_evidenced
    assert "IA-5(1)" in ev.controls_evidenced
    assert ev.content["rotation_state"] == "configured_within_recommended"
    assert ev.content["automatically_after_days"] == 30
    assert ev.content["has_rotation_lambda"] is True


def test_no_secret_resources_emits_nothing() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "no_secrets.tf")
    assert results == []


def test_unpaired_secret_emits_negative_evidence() -> None:
    secret = TerraformResource(
        type="aws_secretsmanager_secret",
        name="api_key",
        body={"name": "api-key"},
        source_ref=SourceRef(file=Path("s.tf"), line_start=1, line_end=5),
    )
    results = detect([secret])
    assert len(results) == 1
    assert results[0].content["rotation_state"] == "absent"
    assert "without a paired" in results[0].content["gap"]


def test_rotation_window_too_long_emits_gap() -> None:
    rotation = TerraformResource(
        type="aws_secretsmanager_secret_rotation",
        name="long_rotation",
        body={
            "secret_id": "x",
            "rotation_lambda_arn": "arn:aws:lambda:us-east-1:123:function:r",
            "rotation_rules": [{"automatically_after_days": 365}],
        },
        source_ref=SourceRef(file=Path("r.tf"), line_start=1, line_end=10),
    )
    results = detect([rotation])
    assert len(results) == 1
    assert results[0].content["rotation_state"] == "configured_window_too_long"
    assert results[0].content["automatically_after_days"] == 365
    assert "365" in results[0].content["gap"]


def test_rotation_without_window_emits_unknown() -> None:
    rotation = TerraformResource(
        type="aws_secretsmanager_secret_rotation",
        name="opaque_window",
        body={
            "secret_id": "x",
            "rotation_lambda_arn": "arn:aws:lambda:us-east-1:123:function:r",
            "rotation_rules": [{"automatically_after_days": "${var.window}"}],
        },
        source_ref=SourceRef(file=Path("r.tf"), line_start=1, line_end=10),
    )
    results = detect([rotation])
    assert len(results) == 1
    assert results[0].content["rotation_state"] == "configured_unknown_window"
