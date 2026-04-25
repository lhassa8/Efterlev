"""Fixture-driven tests for `aws.elb_access_logs`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.elb_access_logs.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "elb_access_logs"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_alb_with_access_logs_emits_enabled_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "alb_with_access_logs.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.elb_access_logs"
    assert ev.ksis_evidenced == ["KSI-MLA-LET"]
    assert "AU-2" in ev.controls_evidenced
    assert "AU-12" in ev.controls_evidenced
    assert ev.content["lb_kind"] == "alb_or_nlb"
    assert ev.content["log_state"] == "enabled"
    assert ev.content["bucket"] == "my-alb-access-logs"


def test_alb_without_access_logs_emits_absent_with_gap() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "alb_no_logs.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["log_state"] == "absent"
    assert "access logs are disabled" in ev.content["gap"]


def test_alb_with_bucket_but_disabled_emits_bucket_only() -> None:
    resource = TerraformResource(
        type="aws_lb",
        name="opted_out",
        body={
            "load_balancer_type": "application",
            "access_logs": [{"enabled": False, "bucket": "logs-bucket"}],
        },
        source_ref=SourceRef(file=Path("lb.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["log_state"] == "bucket_only"


def test_classic_elb_with_access_logs_emits_enabled() -> None:
    resource = TerraformResource(
        type="aws_elb",
        name="legacy",
        body={
            "name": "legacy-elb",
            "access_logs": [{"enabled": True, "bucket": "elb-logs-bucket", "interval": 60}],
        },
        source_ref=SourceRef(file=Path("elb.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["lb_kind"] == "classic"
    assert results[0].content["log_state"] == "enabled"
    assert results[0].content["interval_minutes"] == 60


def test_aws_alb_alias_treated_same_as_aws_lb() -> None:
    """The aws_alb resource is a deprecated alias for aws_lb."""
    resource = TerraformResource(
        type="aws_alb",
        name="legacy_alias",
        body={
            "load_balancer_type": "application",
            "access_logs": [{"enabled": True, "bucket": "logs"}],
        },
        source_ref=SourceRef(file=Path("alb.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["lb_kind"] == "alb_or_nlb"
    assert results[0].content["log_state"] == "enabled"


def test_non_lb_resource_ignored() -> None:
    resource = TerraformResource(
        type="aws_lb_listener",
        name="listener",
        body={"protocol": "HTTPS"},
        source_ref=SourceRef(file=Path("l.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []
