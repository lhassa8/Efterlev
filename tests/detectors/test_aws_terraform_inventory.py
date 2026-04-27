"""Fixture-driven tests for `aws.terraform_inventory`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.terraform_inventory.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "terraform_inventory"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ----------------------------------------------------------


def test_multi_resource_workspace_emits_one_summary_evidence() -> None:
    """A workspace with several resource types emits exactly one inventory
    summary, not one evidence per resource."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "multi_resource.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.terraform_inventory"
    assert ev.ksis_evidenced == ["KSI-PIY-GIV"]
    assert set(ev.controls_evidenced) == {"CM-8", "CM-8(1)"}
    content = ev.content
    assert content["resource_type"] == "terraform_inventory"
    assert content["resource_name"] == "(workspace)"
    assert content["inventory_state"] == "tracked"
    assert content["total_resources"] == 7  # 3 buckets + 2 roles + 1 kms + 1 vpc
    assert content["distinct_resource_types"] == 4
    # Top types sorted by count desc, name asc.
    top = content["top_resource_types"]
    assert top[0] == {"resource_type": "aws_s3_bucket", "count": 3}
    assert top[1] == {"resource_type": "aws_iam_role", "count": 2}


def test_top_types_capped_at_ten(tmp_path: Path) -> None:
    """A workspace with >10 resource types reports only the top 10 to keep
    the evidence content tight."""
    # Generate 15 distinct resource types, each with one declaration.
    parts = [
        f'resource "aws_type_{i}" "x" {{ name = "x" }}\n'  # synthetic types are fine
        for i in range(15)
    ]
    (tmp_path / "many.tf").write_text("".join(parts))
    results = _run_detector_on(tmp_path / "many.tf")
    [ev] = results
    assert ev.content["distinct_resource_types"] == 15
    assert len(ev.content["top_resource_types"]) == 10


# --- should_not_match ------------------------------------------------------


def test_empty_workspace_emits_no_evidence() -> None:
    """A file with no resources (variables/locals/outputs only) yields no
    inventory evidence — the customer hasn't declared anything yet."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "empty.tf")
    assert results == []


def test_empty_resource_list_is_clean_noop() -> None:
    """Direct-call protection: passing [] yields []."""
    assert detect([]) == []


# --- mapping metadata ------------------------------------------------------


def test_detector_registration_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.terraform_inventory"]
    assert spec.ksis == ("KSI-PIY-GIV",)
    assert "CM-8" in spec.controls
    assert "CM-8(1)" in spec.controls
    assert spec.source == "terraform"
