"""Fixture-driven tests for `aws.kms_customer_managed_keys`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.kms_customer_managed_keys.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "kms_customer_managed_keys"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_app_data_cmk_emits_inventory() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "app_data_cmk.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.kms_customer_managed_keys"
    assert ev.ksis_evidenced == ["KSI-SVC-ASM"]
    assert "SC-12" in ev.controls_evidenced
    assert ev.content["description"] == "Application data encryption key"
    assert ev.content["key_usage"] == "ENCRYPT_DECRYPT"
    assert ev.content["deletion_window_in_days"] == 30


def test_no_kms_resource_emits_nothing() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "no_kms.tf")
    assert results == []


def test_sign_verify_key_usage_captured() -> None:
    resource = TerraformResource(
        type="aws_kms_key",
        name="signing_key",
        body={"description": "asymmetric signing", "key_usage": "SIGN_VERIFY"},
        source_ref=SourceRef(file=Path("kms.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["key_usage"] == "SIGN_VERIFY"


def test_minimal_kms_key_uses_default_usage() -> None:
    resource = TerraformResource(
        type="aws_kms_key",
        name="bare",
        body={"description": "minimal"},
        source_ref=SourceRef(file=Path("kms.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["key_usage"] == "ENCRYPT_DECRYPT"
    assert results[0].content["is_enabled"] is True


def test_multiple_kms_keys_emit_one_each() -> None:
    resources = [
        TerraformResource(
            type="aws_kms_key",
            name=f"k_{i}",
            body={"description": f"k_{i}"},
            source_ref=SourceRef(file=Path("kms.tf"), line_start=1, line_end=5),
        )
        for i in range(3)
    ]
    assert len(detect(resources)) == 3
