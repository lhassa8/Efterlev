"""Fixture-driven tests for `aws.cloudwatch_alarms_critical`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.cloudwatch_alarms_critical.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "cloudwatch_alarms_critical"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_root_login_alarm_emits_inventory_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "root_login_alarm.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.cloudwatch_alarms_critical"
    assert set(ev.ksis_evidenced) == {"KSI-MLA-OSM", "KSI-MLA-LET"}
    assert "SI-4" in ev.controls_evidenced
    assert "AU-6(1)" in ev.controls_evidenced
    assert ev.content["resource_name"] == "root_login"
    assert ev.content["metric_name"] == "RootAccountUsageCount"
    assert ev.content["namespace"] == "CWLogs"
    assert ev.content["has_alarm_action"] is True


def test_no_alarm_resource_emits_nothing() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "no_alarms.tf")
    assert results == []


def test_alarm_without_alarm_actions_still_emits_but_flags_missing_action() -> None:
    resource = TerraformResource(
        type="aws_cloudwatch_metric_alarm",
        name="silent_alarm",
        body={
            "alarm_name": "silent",
            "comparison_operator": "GreaterThanThreshold",
            "metric_name": "IAMPolicyChanges",
            "namespace": "CWLogs",
            "threshold": 1,
        },
        source_ref=SourceRef(file=Path("alarm.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["has_alarm_action"] is False


def test_multiple_alarms_emit_one_evidence_each() -> None:
    resources = [
        TerraformResource(
            type="aws_cloudwatch_metric_alarm",
            name=f"alarm_{i}",
            body={"metric_name": f"M{i}", "alarm_actions": ["arn:aws:sns:..."]},
            source_ref=SourceRef(file=Path("a.tf"), line_start=1, line_end=5),
        )
        for i in range(3)
    ]
    assert len(detect(resources)) == 3


def test_non_alarm_resource_ignored() -> None:
    resource = TerraformResource(
        type="aws_s3_bucket",
        name="b",
        body={},
        source_ref=SourceRef(file=Path("s3.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []
