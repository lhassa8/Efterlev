"""Fixture-driven tests for `aws.iam_service_account_keys_age`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.iam_service_account_keys_age.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "iam_service_account_keys_age"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_service_account_with_access_key_emits_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "ci_user_keys.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.iam_service_account_keys_age"
    assert ev.ksis_evidenced == ["KSI-IAM-SNU"]
    assert "IA-2" in ev.controls_evidenced
    assert "IA-5" in ev.controls_evidenced
    assert ev.content["profile_kind"] == "service_account"
    assert ev.content["user_ref"] == "ci-deployer"
    assert ev.content["rotation_visibility"] == "iac_cannot_show_age"


def test_user_without_access_keys_emits_nothing() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "no_access_keys.tf")
    assert results == []


def test_human_user_with_keys_classified_correctly() -> None:
    """A user with both an access key AND a login profile is human-with-keys."""
    src = SourceRef(file=Path("u.tf"), line_start=1, line_end=5)
    user = TerraformResource(type="aws_iam_user", name="dev", body={"name": "dev"}, source_ref=src)
    profile = TerraformResource(
        type="aws_iam_user_login_profile",
        name="dev_login",
        body={"user": "dev"},
        source_ref=src,
    )
    key = TerraformResource(
        type="aws_iam_access_key",
        name="dev_key",
        body={"user": "dev"},
        source_ref=src,
    )
    results = detect([user, profile, key])
    assert len(results) == 1
    assert results[0].content["profile_kind"] == "human_user_with_keys"


def test_multiple_access_keys_emit_one_each() -> None:
    src = SourceRef(file=Path("u.tf"), line_start=1, line_end=5)
    keys = [
        TerraformResource(
            type="aws_iam_access_key",
            name=f"k_{i}",
            body={"user": f"sa_{i}"},
            source_ref=src,
        )
        for i in range(3)
    ]
    results = detect(keys)
    assert len(results) == 3
    for ev in results:
        assert ev.content["profile_kind"] == "service_account"


def test_non_access_key_resource_ignored() -> None:
    resource = TerraformResource(
        type="aws_iam_user",
        name="just_a_user",
        body={"name": "just-a-user"},
        source_ref=SourceRef(file=Path("u.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []
