"""Fixture-driven tests for `aws.cloudfront_viewer_protocol_https`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.cloudfront_viewer_protocol_https.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "cloudfront_viewer_protocol_https"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


# --- should_match ----------------------------------------------------------


def test_redirect_to_https_distribution_emits_https_only() -> None:
    """Distribution with redirect-to-https default + https-only ordered behavior
    + TLSv1.2_2021 minimum protocol = best-shape evidence."""
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "redirect_to_https.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.cloudfront_viewer_protocol_https"
    assert ev.ksis_evidenced == ["KSI-SVC-VCM"]
    assert set(ev.controls_evidenced) == {"SC-23", "SI-7(1)"}
    content = ev.content
    assert content["resource_name"] == "secure"
    assert content["viewer_state"] == "https_only"
    assert content["behavior_count"] == 2
    assert content["minimum_protocol_version"] == "TLSv1.2_2021"
    assert content["tls_meets_fedramp_bar"] is True
    assert "gap" not in content


# --- should_not_match ------------------------------------------------------


def test_allow_all_distribution_emits_gap() -> None:
    """Distribution with allow-all viewer policy + cloudfront default cert (no
    minimum_protocol_version) yields two-part gap."""
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "allow_all.tf")
    assert len(results) == 1
    ev = results[0]
    content = ev.content
    assert content["viewer_state"] == "allows_http"
    assert content["minimum_protocol_version"] is None
    assert content["tls_meets_fedramp_bar"] is False
    assert "gap" in content
    assert "plaintext HTTP" in content["gap"]
    assert "minimum_protocol_version" in content["gap"]


def test_no_cloudfront_resources_emits_nothing() -> None:
    """A codebase with non-cloudfront resources produces no evidence — the
    detector is anchored on the resource type."""
    resource = TerraformResource(
        type="aws_s3_bucket",
        name="data",
        body={"bucket": "example"},
        source_ref=SourceRef(file=Path("s3.tf"), line_start=1, line_end=3),
    )
    assert detect([resource]) == []


def test_empty_resource_list() -> None:
    assert detect([]) == []


# --- mixed-state classification -------------------------------------------


def test_mixed_behaviors_emit_mixed_or_allows_http() -> None:
    """A distribution with default=https-only AND ordered=allow-all classifies
    as `allows_http` because at least one behavior accepts HTTP."""
    resource = TerraformResource(
        type="aws_cloudfront_distribution",
        name="mixed",
        body={
            "default_cache_behavior": {"viewer_protocol_policy": "https-only"},
            "ordered_cache_behavior": [
                {"path_pattern": "/legacy/*", "viewer_protocol_policy": "allow-all"},
            ],
            "viewer_certificate": {"minimum_protocol_version": "TLSv1.2_2021"},
        },
        source_ref=SourceRef(file=Path("mixed.tf"), line_start=1, line_end=20),
    )
    results = detect([resource])
    assert len(results) == 1
    content = results[0].content
    assert content["viewer_state"] == "allows_http"
    assert content["tls_meets_fedramp_bar"] is True
    # Gap covers the http-allowing behavior, but TLS bar is met so only
    # the protocol-policy half of the gap appears.
    assert "plaintext HTTP" in content["gap"]
    assert "minimum_protocol_version" not in content["gap"]


def test_below_bar_tls_emits_tls_gap() -> None:
    """https-only viewer policy but TLSv1 minimum = gap on TLS only."""
    resource = TerraformResource(
        type="aws_cloudfront_distribution",
        name="weak_tls",
        body={
            "default_cache_behavior": {"viewer_protocol_policy": "redirect-to-https"},
            "viewer_certificate": {"minimum_protocol_version": "TLSv1"},
        },
        source_ref=SourceRef(file=Path("weak.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    content = results[0].content
    assert content["viewer_state"] == "https_only"
    assert content["minimum_protocol_version"] == "TLSv1"
    assert content["tls_meets_fedramp_bar"] is False
    assert "gap" in content
    assert "TLSv1.2_2018+" in content["gap"]
    assert "plaintext HTTP" not in content["gap"]


# --- mapping metadata ------------------------------------------------------


def test_detector_registered_with_expected_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.cloudfront_viewer_protocol_https"]
    assert spec.ksis == ("KSI-SVC-VCM",)
    assert "SC-23" in spec.controls
    assert "SI-7(1)" in spec.controls
    assert spec.source == "terraform"
