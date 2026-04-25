"""Fixture-driven tests for `aws.rds_public_accessibility`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.rds_public_accessibility.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "rds_public_accessibility"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_publicly_accessible_db_emits_finding() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "public_db.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.rds_public_accessibility"
    assert set(ev.ksis_evidenced) == {"KSI-CNA-RNT", "KSI-CNA-MAT"}
    assert "AC-3" in ev.controls_evidenced
    assert "SC-7" in ev.controls_evidenced
    assert ev.content["resource_type"] == "aws_db_instance"
    assert ev.content["resource_name"] == "public"
    assert ev.content["exposure_state"] == "publicly_accessible"
    assert "publicly_accessible" in ev.content["gap"]


def test_private_db_emits_no_evidence() -> None:
    """publicly_accessible = false is the safe default — no evidence."""
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "private_db.tf")
    assert results == []


def test_db_without_publicly_accessible_attribute_emits_nothing() -> None:
    """Absent attribute means AWS default (false) — also safe."""
    resource = TerraformResource(
        type="aws_db_instance",
        name="default_private",
        body={"identifier": "x", "engine": "postgres"},
        source_ref=SourceRef(file=Path("rds.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []


def test_rds_cluster_publicly_accessible_emits_finding() -> None:
    resource = TerraformResource(
        type="aws_rds_cluster",
        name="public_cluster",
        body={"engine": "aurora-postgresql", "publicly_accessible": True},
        source_ref=SourceRef(file=Path("cluster.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["resource_type"] == "aws_rds_cluster"


def test_unresolved_interpolation_emits_unparseable() -> None:
    resource = TerraformResource(
        type="aws_db_instance",
        name="conditional",
        body={"identifier": "x", "publicly_accessible": "${var.expose_db}"},
        source_ref=SourceRef(file=Path("rds.tf"), line_start=1, line_end=5),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["exposure_state"] == "unparseable"
    assert "unresolved" in results[0].content["reason"]


def test_non_rds_resource_ignored() -> None:
    resource = TerraformResource(
        type="aws_s3_bucket",
        name="not_rds",
        body={"publicly_accessible": True},  # not a real S3 attr but tests scoping
        source_ref=SourceRef(file=Path("s3.tf"), line_start=1, line_end=5),
    )
    assert detect([resource]) == []
