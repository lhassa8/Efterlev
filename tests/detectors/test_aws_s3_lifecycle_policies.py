"""Fixture-driven tests for `aws.s3_lifecycle_policies`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.s3_lifecycle_policies.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "s3_lifecycle_policies"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ----------------------------------------------------------


def test_lifecycle_with_expiration_emits_configured() -> None:
    """The canonical KSI-SVC-RUD evidence: lifecycle config with at least
    one enabled rule containing an `expiration` block. Evidences both
    SI-12 and SI-12(3)."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "with_expiration.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.s3_lifecycle_policies"
    assert ev.ksis_evidenced == ["KSI-SVC-RUD"]
    assert set(ev.controls_evidenced) == {"SI-12", "SI-12(3)"}
    content = ev.content
    assert content["resource_name"] == "audit_logs"
    assert content["lifecycle_state"] == "configured_with_expiration"
    assert content["rule_count"] == 2
    assert content["enabled_rule_count"] == 2
    assert content["expiration_rule_count"] == 1
    assert content["transition_rule_count"] == 1
    assert "gap" not in content


# --- should_not_match ------------------------------------------------------


def test_transitions_only_emits_no_expiration_with_gap() -> None:
    """Transitions reduce cost but don't evidence SI-12(3) Destruction.
    Only SI-12 fires, with a gap field naming the missing piece."""
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "transitions_only.tf"
    )
    assert len(results) == 1
    ev = results[0]
    content = ev.content
    assert content["lifecycle_state"] == "configured_no_expiration"
    assert content["expiration_rule_count"] == 0
    assert content["transition_rule_count"] == 2
    assert ev.controls_evidenced == ["SI-12"]
    assert "transitions alone" in content["gap"]


def test_disabled_rules_emit_placeholder_with_gap() -> None:
    """A rule declared with status=Disabled is inactive; the resource is
    a placeholder. SI-12 fires structurally only."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "disabled_only.tf")
    assert len(results) == 1
    ev = results[0]
    content = ev.content
    assert content["lifecycle_state"] == "placeholder"
    assert content["rule_count"] == 1
    assert content["enabled_rule_count"] == 0
    assert ev.controls_evidenced == ["SI-12"]
    assert "placeholder" in content["gap"]


def test_no_lifecycle_resources_emits_nothing(tmp_path: Path) -> None:
    """A bucket without an associated lifecycle configuration produces
    no evidence — silence is correct, the Gap Agent classifies based
    on absence."""
    (tmp_path / "bucket_only.tf").write_text(
        'resource "aws_s3_bucket" "lonely" {\n  bucket = "lonely"\n}\n'
    )
    assert _run_detector_on(tmp_path / "bucket_only.tf") == []


# --- mapping metadata ------------------------------------------------------


def test_detector_registration_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.s3_lifecycle_policies"]
    assert spec.ksis == ("KSI-SVC-RUD",)
    assert "SI-12" in spec.controls
    assert "SI-12(3)" in spec.controls
    assert spec.source == "terraform"
