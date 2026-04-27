"""Fixture-driven tests for `aws.iam_admin_policy_usage`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.iam_admin_policy_usage.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "iam_admin_policy_usage"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_admin_attached_to_role_emits_finding() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "admin_role.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.iam_admin_policy_usage"
    # KSI-IAM-JIT cross-mapped 2026-04-27 (Priority 1.10): AC-6 is in
    # KSI-IAM-JIT's FRMR controls array, so an AdministratorAccess
    # attachment is also evidence against JIT.
    assert ev.ksis_evidenced == ["KSI-IAM-ELP", "KSI-IAM-JIT"]
    assert "AC-6" in ev.controls_evidenced
    assert "AC-6(2)" in ev.controls_evidenced
    assert ev.content["principal_kind"] == "role"
    assert ev.content["principal_ref"] == "break-glass"
    assert "break-glass" in ev.content["gap"]


def test_scoped_managed_policy_emits_nothing() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "scoped_role.tf")
    assert results == []


def test_admin_attached_to_user_emits_finding() -> None:
    resource = TerraformResource(
        type="aws_iam_user_policy_attachment",
        name="admin_user",
        body={
            "user": "powerful-dev",
            "policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess",
        },
        source_ref=SourceRef(file=Path("u.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["principal_kind"] == "user"
    assert results[0].content["principal_ref"] == "powerful-dev"


def test_admin_attached_to_group_emits_finding() -> None:
    resource = TerraformResource(
        type="aws_iam_group_policy_attachment",
        name="admins_group",
        body={
            "group": "admins",
            "policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess",
        },
        source_ref=SourceRef(file=Path("g.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["principal_kind"] == "group"


def test_inline_role_policy_resource_ignored() -> None:
    """Inline policy resources are scoped to a different detector."""
    resource = TerraformResource(
        type="aws_iam_role_policy",
        name="inline",
        body={"role": "x", "policy": '{"Version":"2012-10-17"}'},
        source_ref=SourceRef(file=Path("p.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []


def test_multiple_admin_attachments_emit_one_each() -> None:
    resources = [
        TerraformResource(
            type="aws_iam_role_policy_attachment",
            name=f"admin_{i}",
            body={
                "role": f"role_{i}",
                "policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess",
            },
            source_ref=SourceRef(file=Path("r.tf"), line_start=1, line_end=5),
        )
        for i in range(3)
    ]
    assert len(detect(resources)) == 3
