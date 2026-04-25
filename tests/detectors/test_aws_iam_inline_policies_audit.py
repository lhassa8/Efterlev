"""Fixture-driven tests for `aws.iam_inline_policies_audit`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.iam_inline_policies_audit.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "iam_inline_policies_audit"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_role_inline_policy_emits_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "role_inline_policy.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.iam_inline_policies_audit"
    assert ev.ksis_evidenced == ["KSI-IAM-ELP"]
    assert "AC-2" in ev.controls_evidenced
    assert "AC-6" in ev.controls_evidenced
    assert ev.content["principal_kind"] == "role"
    assert ev.content["principal_ref"] == "lambda-exec"
    assert ev.content["policy_state"] == "literal_json"
    assert ev.content["policy_name"] == "lambda-exec-inline"


def test_managed_policy_attachment_emits_nothing() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "managed_policy_attachment.tf")
    assert results == []


def test_user_inline_policy_emits_evidence() -> None:
    resource = TerraformResource(
        type="aws_iam_user_policy",
        name="dev_user_inline",
        body={"name": "dev-inline", "user": "dev-user", "policy": '{"Version":"2012-10-17"}'},
        source_ref=SourceRef(file=Path("u.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["principal_kind"] == "user"
    assert results[0].content["principal_ref"] == "dev-user"


def test_group_inline_policy_emits_evidence() -> None:
    resource = TerraformResource(
        type="aws_iam_group_policy",
        name="ops_inline",
        body={"name": "ops-inline", "group": "ops", "policy": '{"Version":"2012-10-17"}'},
        source_ref=SourceRef(file=Path("g.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["principal_kind"] == "group"


def test_jsonencode_policy_marked_unparseable() -> None:
    resource = TerraformResource(
        type="aws_iam_role_policy",
        name="dynamic",
        body={
            "name": "dynamic",
            "role": "x",
            "policy": "${jsonencode(local.policy_doc)}",
        },
        source_ref=SourceRef(file=Path("d.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["policy_state"] == "unparseable"


def test_non_inline_policy_resource_ignored() -> None:
    """`aws_iam_policy` (managed-policy declaration) is NOT inline."""
    resource = TerraformResource(
        type="aws_iam_policy",
        name="managed",
        body={"name": "managed", "policy": '{"Version":"2012-10-17"}'},
        source_ref=SourceRef(file=Path("m.tf"), line_start=1, line_end=10),
    )
    assert detect([resource]) == []
