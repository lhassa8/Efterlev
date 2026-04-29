"""Fixture-driven tests for `aws.centralized_log_aggregation`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.centralized_log_aggregation.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "centralized_log_aggregation"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def _ref() -> SourceRef:
    return SourceRef(file=Path("logs.tf"), line_start=1, line_end=10)


# --- fixture-driven posture tests -------------------------------------------


def test_aggregated_emits_evidence_with_full_si_4_set() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "aggregated.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.centralized_log_aggregation"
    assert "KSI-MLA-OSM" in ev.ksis_evidenced
    assert ev.content["aggregation_state"] == "aggregated"
    # Both producers and aggregators present.
    assert ev.content["log_producer_count"] >= 1
    assert ev.content["aggregator_count"] >= 1
    # SI-4(2) and SI-4(4) only fire in `aggregated` state.
    assert "SI-4(2)" in ev.controls_evidenced
    assert "SI-4(4)" in ev.controls_evidenced
    # AU-2/3/4 always fire when at least one resource is present.
    assert "AU-2" in ev.controls_evidenced
    # Aggregated posture has no gap text.
    assert "gap" not in ev.content


def test_producers_only_emits_evidence_with_gap_and_no_si_4() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "producers_only.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["aggregation_state"] == "producers_only"
    assert ev.content["log_producer_count"] >= 1
    assert ev.content["aggregator_count"] == 0
    # SI-4 enhancements should NOT fire without aggregators.
    assert "SI-4(2)" not in ev.controls_evidenced
    assert "SI-4(4)" not in ev.controls_evidenced
    # AU-2 still evidenced — log producers exist.
    assert "AU-2" in ev.controls_evidenced
    assert "gap" in ev.content
    assert "no centralization primitive" in ev.content["gap"]


def test_aggregators_only_emits_evidence_with_gap() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "aggregators_only.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["aggregation_state"] == "aggregators_only"
    assert ev.content["log_producer_count"] == 0
    assert ev.content["aggregator_count"] >= 1
    assert "SI-4(2)" not in ev.controls_evidenced
    assert "gap" in ev.content
    assert "no log-producing resources" in ev.content["gap"]


def test_no_logging_emits_no_evidence() -> None:
    # Workspace with neither producers nor aggregators → 0 Evidence.
    # The Gap Agent should classify KSI-MLA-OSM appropriately
    # (likely evidence_layer_inapplicable) based on absence.
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "no_logging.tf")
    assert results == []


# --- per-type breakdown ----------------------------------------------------


def test_log_producers_by_type_breakdown_is_accurate() -> None:
    cwlg = TerraformResource(
        type="aws_cloudwatch_log_group", name="app", body={}, source_ref=_ref()
    )
    ct = TerraformResource(type="aws_cloudtrail", name="audit", body={}, source_ref=_ref())
    fl_a = TerraformResource(type="aws_flow_log", name="vpc_a", body={}, source_ref=_ref())
    fl_b = TerraformResource(type="aws_flow_log", name="vpc_b", body={}, source_ref=_ref())
    sh = TerraformResource(type="aws_securityhub_account", name="main", body={}, source_ref=_ref())
    results = detect([cwlg, ct, fl_a, fl_b, sh])
    assert len(results) == 1
    ev = results[0]
    assert ev.content["log_producers_by_type"] == {
        "aws_cloudwatch_log_group": 1,
        "aws_cloudtrail": 1,
        "aws_flow_log": 2,
    }
    assert ev.content["aggregators_by_type"] == {"aws_securityhub_account": 1}
    assert ev.content["log_producer_count"] == 4
    assert ev.content["aggregator_count"] == 1


# --- aggregator-only paths cover each recognized type ----------------------


def test_each_aggregator_type_counts() -> None:
    aggregator_types = [
        "aws_securityhub_account",
        "aws_securityhub_finding_aggregator",
        "aws_cloudwatch_log_destination",
        "aws_cloudwatch_log_subscription_filter",
        "aws_kinesis_firehose_delivery_stream",
        "aws_opensearch_domain",
        "aws_elasticsearch_domain",
    ]
    resources = [
        TerraformResource(type=t, name=f"r_{i}", body={}, source_ref=_ref())
        for i, t in enumerate(aggregator_types)
    ]
    # Add one producer so we get the `aggregated` state.
    resources.append(
        TerraformResource(type="aws_cloudwatch_log_group", name="p", body={}, source_ref=_ref())
    )
    results = detect(resources)
    assert len(results) == 1
    ev = results[0]
    # Every aggregator type should be in the breakdown with count 1.
    for t in aggregator_types:
        assert ev.content["aggregators_by_type"].get(t) == 1
    assert ev.content["aggregation_state"] == "aggregated"


# --- KSI mapping -----------------------------------------------------------


def test_evidence_carries_ksi_mla_osm() -> None:
    cwlg = TerraformResource(
        type="aws_cloudwatch_log_group", name="app", body={}, source_ref=_ref()
    )
    sh = TerraformResource(type="aws_securityhub_account", name="main", body={}, source_ref=_ref())
    results = detect([cwlg, sh])
    assert len(results) == 1
    assert results[0].ksis_evidenced == ["KSI-MLA-OSM"]
