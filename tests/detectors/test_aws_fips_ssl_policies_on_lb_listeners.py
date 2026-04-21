"""Fixture-driven tests for `aws.fips_ssl_policies_on_lb_listeners`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.fips_ssl_policies_on_lb_listeners.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "fips_ssl_policies_on_lb_listeners"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_tls13_policy_emits_present_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "tls13_policy.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.fips_ssl_policies_on_lb_listeners"
    assert set(ev.ksis_evidenced) == {"KSI-SVC-VRI", "KSI-SVC-SNT"}
    assert ev.controls_evidenced == ["SC-13"]
    assert ev.content["fips_state"] == "present"
    assert ev.content["ssl_policy"] == "ELBSecurityPolicy-TLS13-1-2-2021-06"


def test_forward_secrecy_policy_emits_present_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "forward_secrecy_policy.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["fips_state"] == "present"
    assert ev.content["ssl_policy"].startswith("ELBSecurityPolicy-FS-")


def test_legacy_policy_emits_absent_evidence_with_gap() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "legacy_policy.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["fips_state"] == "absent"
    assert ev.content["ssl_policy"] == "ELBSecurityPolicy-2016-08"
    assert "FIPS-aligned" in ev.content["gap"]


def test_http_listener_is_skipped_entirely() -> None:
    # HTTP listeners are outside this detector's scope — aws.tls_on_lb_listeners
    # covers the "should this be TLS at all?" question. Emitting evidence here
    # would duplicate that signal.
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "http_listener.tf")
    assert results == []


def test_detector_registered_with_expected_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.fips_ssl_policies_on_lb_listeners"]
    assert set(spec.ksis) == {"KSI-SVC-VRI", "KSI-SVC-SNT"}
    assert spec.controls == ("SC-13",)
    assert spec.source == "terraform"
