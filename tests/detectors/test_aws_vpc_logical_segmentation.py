"""Fixture-driven tests for `aws.vpc_logical_segmentation`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.vpc_logical_segmentation.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "vpc_logical_segmentation"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ----------------------------------------------------------


def test_vpc_with_private_and_public_subnets_emits_declared() -> None:
    """The canonical KSI-CNA-ULN evidence: VPC + both subnet tiers.
    Evidences SC-7 AND SC-7(7) (split-tier subsystem separation)."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "declared.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.vpc_logical_segmentation"
    assert ev.ksis_evidenced == ["KSI-CNA-ULN"]
    assert set(ev.controls_evidenced) == {"SC-7", "SC-7(7)"}
    content = ev.content
    assert content["resource_type"] == "aws_vpc"
    assert content["resource_name"] == "main"
    assert content["cidr_block"] == "10.0.0.0/16"
    assert content["subnet_count"] == 4
    assert content["private_subnet_count"] == 2
    assert content["public_subnet_count"] == 2
    assert content["segmentation_state"] == "declared"
    assert "gap" not in content


# --- should_not_match ------------------------------------------------------


def test_vpc_with_only_private_subnets_emits_single_tier() -> None:
    """Private-only VPC evidences SC-7 but not SC-7(7); the gap field names
    which tier is missing."""
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_not_match" / "single_tier_private.tf"
    )
    assert len(results) == 1
    ev = results[0]
    content = ev.content
    assert content["segmentation_state"] == "single_tier"
    assert content["public_subnet_count"] == 0
    assert content["private_subnet_count"] == 2
    assert ev.controls_evidenced == ["SC-7"]
    assert "private-only" in content["gap"]


def test_vpc_with_no_subnets_emits_undefined() -> None:
    """A VPC declared without subnets in the same codebase produces an
    `undefined` evidence. Subnets may live in another module — agents
    can resolve via Evidence Manifests if the customer attests to that."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "undefined.tf")
    assert len(results) == 1
    ev = results[0]
    content = ev.content
    assert content["segmentation_state"] == "undefined"
    assert content["subnet_count"] == 0
    assert ev.controls_evidenced == ["SC-7"]
    assert "no subnets matched" in content["gap"]


def test_no_vpc_resources_emits_nothing(tmp_path: Path) -> None:
    """A codebase with subnets but no VPC declaration produces no evidence —
    the detector is anchored on `aws_vpc`."""
    (tmp_path / "subnets_only.tf").write_text(
        'resource "aws_subnet" "orphan" {\n  cidr_block = "10.30.0.0/24"\n}\n'
    )
    results = _run_detector_on(tmp_path / "subnets_only.tf")
    assert results == []


# --- mapping metadata ------------------------------------------------------


def test_detector_registration_metadata() -> None:
    """Priority 1.1 (2026-04-27): aws.vpc_logical_segmentation evidences
    KSI-CNA-ULN against SC-7 / SC-7(7) per FRMR 0.9.43-beta."""
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.vpc_logical_segmentation"]
    assert spec.ksis == ("KSI-CNA-ULN",)
    assert "SC-7" in spec.controls
    assert "SC-7(7)" in spec.controls
    assert spec.source == "terraform"
