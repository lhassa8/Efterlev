"""Fixture-driven tests for `aws.suspicious_activity_response`."""

from __future__ import annotations

import json
from pathlib import Path

from efterlev.detectors.aws.suspicious_activity_response.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "suspicious_activity_response"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


# --- should_match ----------------------------------------------------------


def test_guardduty_rule_with_lambda_target_emits_wired() -> None:
    """Rule sourced from `aws.guardduty` with a Lambda target — wired."""
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "guardduty_to_lambda.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.suspicious_activity_response"
    assert ev.ksis_evidenced == ["KSI-IAM-SUS"]
    assert set(ev.controls_evidenced) == {"AC-2", "AC-2(13)"}
    content = ev.content
    assert content["resource_name"] == "guardduty_findings"
    assert content["response_state"] == "wired"
    assert content["matched_sources"] == ["aws.guardduty"]
    assert content["target_count"] == 1
    assert content["target_summary"] == ["lambda"]
    assert "gap" not in content


# --- should_not_match ------------------------------------------------------


def test_non_security_rules_emit_nothing() -> None:
    """EventBridge rules sourced from non-security AWS services (aws.ec2,
    schedule_expression) produce no evidence — the detector is anchored on
    finding-source matches."""
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "non_security_rule.tf")
    assert results == []


def test_empty_resource_list() -> None:
    assert detect([]) == []


# --- edge-case classification ---------------------------------------------


def test_security_hub_rule_with_no_target_emits_no_target_gap() -> None:
    """A rule sourced from aws.securityhub with no target lands in
    `no_target` and emits a gap field."""
    rule = TerraformResource(
        type="aws_cloudwatch_event_rule",
        name="orphan_securityhub",
        body={
            "name": "orphan",
            "event_pattern": json.dumps(
                {"source": ["aws.securityhub"], "detail-type": ["Security Hub Findings"]}
            ),
        },
        source_ref=SourceRef(file=Path("rule.tf"), line_start=1, line_end=10),
    )
    results = detect([rule])
    assert len(results) == 1
    content = results[0].content
    assert content["response_state"] == "no_target"
    assert content["matched_sources"] == ["aws.securityhub"]
    assert content["target_count"] == 0
    assert "gap" in content
    assert "aws.securityhub" in content["gap"]
    assert "no `aws_cloudwatch_event_target` attached" in content["gap"]


def test_multiple_finding_sources_matched() -> None:
    """A rule whose event_pattern matches multiple finding sources reports
    all of them in matched_sources."""
    rule = TerraformResource(
        type="aws_cloudwatch_event_rule",
        name="all_findings",
        body={
            "event_pattern": json.dumps(
                {"source": ["aws.guardduty", "aws.securityhub", "aws.macie2"]}
            ),
        },
        source_ref=SourceRef(file=Path("rule.tf"), line_start=1, line_end=10),
    )
    target = TerraformResource(
        type="aws_cloudwatch_event_target",
        name="responder",
        body={
            "rule": "${aws_cloudwatch_event_rule.all_findings.name}",
            "arn": "arn:aws:states:us-east-1:111122223333:stateMachine:Responder",
        },
        source_ref=SourceRef(file=Path("t.tf"), line_start=1, line_end=5),
    )
    results = detect([rule, target])
    assert len(results) == 1
    content = results[0].content
    assert content["matched_sources"] == ["aws.guardduty", "aws.macie2", "aws.securityhub"]
    assert content["response_state"] == "wired"
    assert content["target_summary"] == ["states"]


def test_event_pattern_placeholder_yields_no_evidence() -> None:
    """An event_pattern built from a data reference renders as a `${...}`
    placeholder; conservatively no match → no evidence emitted."""
    rule = TerraformResource(
        type="aws_cloudwatch_event_rule",
        name="indirect",
        body={"event_pattern": "${data.aws_cloudwatch_event_pattern.findings.json}"},
        source_ref=SourceRef(file=Path("rule.tf"), line_start=1, line_end=5),
    )
    assert detect([rule]) == []


def test_invalid_json_event_pattern_yields_no_evidence() -> None:
    """A malformed event_pattern is conservatively skipped (not a finding)."""
    rule = TerraformResource(
        type="aws_cloudwatch_event_rule",
        name="malformed",
        body={"event_pattern": "{ this is not json"},
        source_ref=SourceRef(file=Path("rule.tf"), line_start=1, line_end=5),
    )
    assert detect([rule]) == []


# --- mapping metadata ------------------------------------------------------


def test_detector_registered_with_expected_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.suspicious_activity_response"]
    assert spec.ksis == ("KSI-IAM-SUS",)
    assert "AC-2" in spec.controls
    assert "AC-2(13)" in spec.controls
    assert spec.source == "terraform"
