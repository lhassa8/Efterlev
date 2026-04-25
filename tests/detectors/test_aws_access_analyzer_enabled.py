"""Fixture-driven tests for `aws.access_analyzer_enabled`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.access_analyzer_enabled.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "access_analyzer_enabled"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_account_scoped_analyzer_emits_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "account_scoped.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.access_analyzer_enabled"
    assert ev.ksis_evidenced == ["KSI-CNA-EIS"]
    assert "CA-7" in ev.controls_evidenced
    assert ev.content["scope"] == "ACCOUNT"
    assert ev.content["stronger_org_scope"] is False


def test_no_analyzer_declared_emits_nothing() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "no_analyzer.tf")
    assert results == []


def test_organization_scoped_analyzer_flags_stronger_coverage() -> None:
    resource = TerraformResource(
        type="aws_accessanalyzer_analyzer",
        name="org_wide",
        body={"analyzer_name": "org-wide", "type": "ORGANIZATION"},
        source_ref=SourceRef(file=Path("aa.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["scope"] == "ORGANIZATION"
    assert results[0].content["stronger_org_scope"] is True


def test_analyzer_without_type_defaults_to_account_scope() -> None:
    """AWS default for `type` on aws_accessanalyzer_analyzer is ACCOUNT."""
    resource = TerraformResource(
        type="aws_accessanalyzer_analyzer",
        name="bare",
        body={"analyzer_name": "bare"},
        source_ref=SourceRef(file=Path("aa.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["scope"] == "ACCOUNT"


def test_multiple_analyzers_emit_one_each() -> None:
    resources = [
        TerraformResource(
            type="aws_accessanalyzer_analyzer",
            name=f"a_{i}",
            body={"analyzer_name": f"a_{i}", "type": "ACCOUNT"},
            source_ref=SourceRef(file=Path("aa.tf"), line_start=1, line_end=5),
        )
        for i in range(2)
    ]
    assert len(detect(resources)) == 2
