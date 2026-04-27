"""Fixture-driven tests for `aws.backup_restore_testing`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.backup_restore_testing.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "backup_restore_testing"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


# --- should_match ----------------------------------------------------------


def test_plan_with_selection_emits_configured_state() -> None:
    """A scheduled plan with a matching selection lands in `configured` —
    the strongest evidence shape."""
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "restore_testing_plan.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.backup_restore_testing"
    assert ev.ksis_evidenced == ["KSI-RPL-TRC"]
    assert set(ev.controls_evidenced) == {"CP-4", "CP-4(1)"}
    content = ev.content
    assert content["resource_name"] == "monthly"
    assert content["testing_state"] == "configured"
    assert content["schedule_expression"] == "cron(0 5 1 * ? *)"
    assert content["start_window_hours"] == 24
    assert content["recovery_point_selection_window_days"] == 7
    assert content["selection_count"] == 1
    assert "gap" not in content


# --- should_not_match ------------------------------------------------------


def test_backup_without_restore_testing_emits_nothing() -> None:
    """Backup vault + backup plan + backup selection without a restore-testing
    plan produces no evidence — the detector is anchored on the
    aws_backup_restore_testing_plan resource type."""
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "backup_only.tf")
    assert results == []


def test_empty_resource_list() -> None:
    assert detect([]) == []


# --- edge-case classification ---------------------------------------------


def test_plan_without_selection_emits_no_selection_gap() -> None:
    """A scheduled plan with NO matching selection lands in `no_selection`
    with a gap field naming the missing piece."""
    plan = TerraformResource(
        type="aws_backup_restore_testing_plan",
        name="orphan",
        body={
            "name": "orphan_plan",
            "schedule_expression": "cron(0 5 * * ? *)",
            "start_window_hours": 24,
            "recovery_point_selection": {
                "algorithm": "LATEST_WITHIN_WINDOW",
                "include_vaults": ["*"],
                "recovery_point_types": ["SNAPSHOT"],
                "selection_window_days": 7,
            },
        },
        source_ref=SourceRef(file=Path("plan.tf"), line_start=1, line_end=20),
    )
    results = detect([plan])
    assert len(results) == 1
    content = results[0].content
    assert content["testing_state"] == "no_selection"
    assert content["selection_count"] == 0
    assert "gap" in content
    assert "no `aws_backup_restore_testing_selection`" in content["gap"]


def test_plan_without_schedule_emits_incomplete_gap() -> None:
    """A plan with no schedule_expression lands in `incomplete`."""
    plan = TerraformResource(
        type="aws_backup_restore_testing_plan",
        name="bare",
        body={
            "name": "bare_plan",
            "recovery_point_selection": {
                "algorithm": "LATEST_WITHIN_WINDOW",
                "include_vaults": ["*"],
                "recovery_point_types": ["SNAPSHOT"],
                "selection_window_days": 7,
            },
        },
        source_ref=SourceRef(file=Path("bare.tf"), line_start=1, line_end=15),
    )
    results = detect([plan])
    assert len(results) == 1
    content = results[0].content
    assert content["testing_state"] == "incomplete"
    assert content["schedule_expression"] is None
    assert "gap" in content
    assert "no `schedule_expression`" in content["gap"]


def test_selection_join_by_terraform_reference() -> None:
    """The detector joins selections to plans by parsing the
    `aws_backup_restore_testing_plan.<name>.id` shape from
    `restore_testing_plan_id`."""
    plan = TerraformResource(
        type="aws_backup_restore_testing_plan",
        name="weekly",
        body={"schedule_expression": "rate(7 days)"},
        source_ref=SourceRef(file=Path("p.tf"), line_start=1, line_end=5),
    )
    selection = TerraformResource(
        type="aws_backup_restore_testing_selection",
        name="weekly_sel",
        body={
            "name": "weekly",
            "restore_testing_plan_id": "${aws_backup_restore_testing_plan.weekly.id}",
            "iam_role_arn": "arn:aws:iam::111122223333:role/Restore",
            "protected_resource_type": "EBS",
        },
        source_ref=SourceRef(file=Path("s.tf"), line_start=1, line_end=10),
    )
    results = detect([plan, selection])
    assert len(results) == 1
    content = results[0].content
    assert content["testing_state"] == "configured"
    assert content["selection_count"] == 1


# --- mapping metadata ------------------------------------------------------


def test_detector_registered_with_expected_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.backup_restore_testing"]
    assert spec.ksis == ("KSI-RPL-TRC",)
    assert "CP-4" in spec.controls
    assert "CP-4(1)" in spec.controls
    assert spec.source == "terraform"
