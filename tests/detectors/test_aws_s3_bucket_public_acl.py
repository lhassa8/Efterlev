"""Fixture-driven tests for `aws.s3_bucket_public_acl`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.s3_bucket_public_acl.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "s3_bucket_public_acl"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_public_read_acl_emits_finding() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "public_read_acl.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.s3_bucket_public_acl"
    assert ev.content["exposure_state"] == "public_acl"
    assert ev.content["acl"] == "public-read"
    assert "public-read" in ev.content["gap"]


def test_public_read_write_acl_emits_finding() -> None:
    resource = TerraformResource(
        type="aws_s3_bucket_acl",
        name="permissive",
        body={"bucket": "x", "acl": "public-read-write"},
        source_ref=SourceRef(file=Path("acl.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["acl"] == "public-read-write"


def test_private_acl_emits_no_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "private_acl.tf")
    assert results == []


def test_authenticated_read_acl_emits_no_evidence() -> None:
    """`authenticated-read` is for any AWS-authenticated principal, not anonymous."""
    resource = TerraformResource(
        type="aws_s3_bucket_acl",
        name="auth_only",
        body={"bucket": "x", "acl": "authenticated-read"},
        source_ref=SourceRef(file=Path("acl.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []


def test_bucket_policy_with_anonymous_allow_emits_finding() -> None:
    policy_json = (
        '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*",'
        '"Action":"s3:GetObject","Resource":"arn:aws:s3:::public-assets/*"}]}'
    )
    resource = TerraformResource(
        type="aws_s3_bucket_policy",
        name="anon_get",
        body={"bucket": "public-assets", "policy": policy_json},
        source_ref=SourceRef(file=Path("policy.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["exposure_state"] == "anonymous_allow"


def test_bucket_policy_with_aws_star_principal_emits_finding() -> None:
    policy_json = (
        '{"Version":"2012-10-17","Statement":['
        '{"Effect":"Allow","Principal":{"AWS":"*"},"Action":"s3:GetObject",'
        '"Resource":"arn:aws:s3:::public-assets/*"}]}'
    )
    resource = TerraformResource(
        type="aws_s3_bucket_policy",
        name="aws_star",
        body={"bucket": "public-assets", "policy": policy_json},
        source_ref=SourceRef(file=Path("policy.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["exposure_state"] == "anonymous_allow"


def test_bucket_policy_with_named_principal_emits_no_evidence() -> None:
    policy_json = (
        '{"Version":"2012-10-17","Statement":['
        '{"Effect":"Allow","Principal":{"AWS":"arn:aws:iam::111122223333:root"},'
        '"Action":"s3:GetObject","Resource":"arn:aws:s3:::trusted/*"}]}'
    )
    resource = TerraformResource(
        type="aws_s3_bucket_policy",
        name="trusted",
        body={"bucket": "trusted", "policy": policy_json},
        source_ref=SourceRef(file=Path("policy.tf"), line_start=1, line_end=10),
    )
    assert detect([resource]) == []


def test_bucket_policy_built_via_jsonencode_is_unparseable() -> None:
    resource = TerraformResource(
        type="aws_s3_bucket_policy",
        name="from_jsonencode",
        body={"bucket": "x", "policy": "${jsonencode(local.bucket_policy)}"},
        source_ref=SourceRef(file=Path("policy.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["exposure_state"] == "unparseable"
    assert "jsonencode" in results[0].content["reason"]
