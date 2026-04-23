"""Tests for `efterlev.terraform.plan.parse_plan_json`.

Plan-JSON fixtures are embedded as Python literals rather than generated
at test time via `terraform show -json` — we do not want Terraform on the
PATH as a test-time dependency. The fixtures mirror the shape a real
plan JSON document produces (verified out-of-band against Terraform 1.14
during the design phase; see DECISIONS 2026-04-22 "Design: Terraform
Plan JSON support").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from efterlev.errors import DetectorError
from efterlev.terraform import parse_plan_json


def _write_plan(tmp_path: Path, payload: dict, name: str = "plan.json") -> Path:
    """Serialize `payload` as a plan-JSON file for the parser to read."""
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


# A minimal but structurally-realistic plan JSON fixture covering the
# patterns the translator must handle:
#   - root-module resources
#   - child-module resources (module.storage)
#   - for_each expansion (two bucket instances with distinct `index`)
#   - mode="data" resource that must be skipped
#   - nested block values (SSE rule → apply_server_side_encryption_by_default)
_STORAGE_PLAN = {
    "format_version": "1.2",
    "terraform_version": "1.14.8",
    "planned_values": {
        "root_module": {
            "resources": [
                {
                    "address": "aws_s3_bucket.logs",
                    "mode": "managed",
                    "type": "aws_s3_bucket",
                    "name": "logs",
                    "values": {"bucket": "logs-bucket"},
                },
                {
                    "address": "data.aws_iam_policy_document.skip_me",
                    "mode": "data",
                    "type": "aws_iam_policy_document",
                    "name": "skip_me",
                    "values": {},
                },
            ],
            "child_modules": [
                {
                    "address": "module.storage",
                    "resources": [
                        {
                            "address": 'module.storage.aws_s3_bucket.this["alpha"]',
                            "mode": "managed",
                            "type": "aws_s3_bucket",
                            "name": "this",
                            "index": "alpha",
                            "values": {"bucket": "app-alpha"},
                        },
                        {
                            "address": 'module.storage.aws_s3_bucket.this["beta"]',
                            "mode": "managed",
                            "type": "aws_s3_bucket",
                            "name": "this",
                            "index": "beta",
                            "values": {"bucket": "app-beta"},
                        },
                        {
                            "address": (
                                "module.storage."
                                'aws_s3_bucket_server_side_encryption_configuration.'
                                'this["alpha"]'
                            ),
                            "mode": "managed",
                            "type": "aws_s3_bucket_server_side_encryption_configuration",
                            "name": "this",
                            "index": "alpha",
                            "values": {
                                "rule": [
                                    {
                                        "apply_server_side_encryption_by_default": [
                                            {"sse_algorithm": "AES256"}
                                        ]
                                    }
                                ]
                            },
                        },
                    ],
                }
            ],
        }
    },
    "configuration": {
        "provider_config": {},
        "root_module": {
            "module_calls": {"storage": {"source": "./modules/storage"}}
        },
    },
}


def test_parses_managed_resources_including_module_expansion(tmp_path: Path) -> None:
    plan_path = _write_plan(tmp_path, _STORAGE_PLAN)
    resources = parse_plan_json(plan_path)

    # 1 root-module bucket + 2 expanded buckets + 1 SSE = 4 (data source skipped).
    assert len(resources) == 4

    types = {r.type for r in resources}
    assert "aws_s3_bucket" in types
    assert "aws_s3_bucket_server_side_encryption_configuration" in types
    # mode="data" resources are skipped.
    assert "aws_iam_policy_document" not in types


def test_for_each_key_becomes_resource_name(tmp_path: Path) -> None:
    plan_path = _write_plan(tmp_path, _STORAGE_PLAN)
    resources = parse_plan_json(plan_path)

    bucket_names = {r.name for r in resources if r.type == "aws_s3_bucket"}
    # Root-module bucket keeps its HCL name; for_each-expanded buckets use
    # their index key (what the user thinks in, e.g. "alpha") rather than
    # the HCL-address label "this".
    assert bucket_names == {"logs", "alpha", "beta"}


def test_nested_block_shape_is_hcl_compatible(tmp_path: Path) -> None:
    # The key design claim: plan JSON's `values.rule.apply_SSE_by_default`
    # has the same list-of-dicts nesting that python-hcl2 emits for HCL
    # input, so `TerraformResource.get_nested(...)` — and therefore every
    # existing detector's body-walking code — works unchanged.
    plan_path = _write_plan(tmp_path, _STORAGE_PLAN)
    resources = parse_plan_json(plan_path)
    sse = next(
        r for r in resources if r.type == "aws_s3_bucket_server_side_encryption_configuration"
    )
    assert (
        sse.get_nested("rule", "apply_server_side_encryption_by_default", "sse_algorithm")
        == "AES256"
    )


def test_source_ref_for_module_resource_points_at_module_source(tmp_path: Path) -> None:
    plan_path = _write_plan(tmp_path, _STORAGE_PLAN)
    resources = parse_plan_json(plan_path)
    alpha = next(r for r in resources if r.type == "aws_s3_bucket" and r.name == "alpha")
    # Module-nested resources anchor on the module source path from
    # configuration.root_module.module_calls.
    assert str(alpha.source_ref.file) == "modules/storage"
    # Plan JSON has no line info — explicitly None, not 0.
    assert alpha.source_ref.line_start is None
    assert alpha.source_ref.line_end is None


def test_source_ref_for_root_resource_falls_back_to_plan_file(tmp_path: Path) -> None:
    plan_path = _write_plan(tmp_path, _STORAGE_PLAN)
    resources = parse_plan_json(plan_path)
    logs = next(r for r in resources if r.type == "aws_s3_bucket" and r.name == "logs")
    # Root-module resources have no module-call entry; we anchor at the
    # plan file itself so downstream renderers have something to show.
    assert str(logs.source_ref.file).endswith("plan.json")


def test_target_root_makes_source_ref_repo_relative(tmp_path: Path) -> None:
    # Plan file lives under tmp_path/repo/; target_root = tmp_path/repo.
    repo = tmp_path / "repo"
    repo.mkdir()
    plan_path = _write_plan(repo, _STORAGE_PLAN, name="plan.json")
    # Create the module dir so the resolved path exists (the parser
    # resolves `./modules/storage` against the plan-file's dir).
    (repo / "modules" / "storage").mkdir(parents=True)

    resources = parse_plan_json(plan_path, target_root=repo)
    alpha = next(r for r in resources if r.type == "aws_s3_bucket" and r.name == "alpha")
    # Repo-relative source_ref per the post-fixup-D contract.
    assert not alpha.source_ref.file.is_absolute()


# --- error paths --------------------------------------------------------


def test_missing_file_raises_detector_error(tmp_path: Path) -> None:
    with pytest.raises(DetectorError, match="plan file not found"):
        parse_plan_json(tmp_path / "does-not-exist.json")


def test_invalid_json_raises_detector_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(DetectorError, match="not valid JSON"):
        parse_plan_json(bad)


def test_non_plan_json_raises_detector_error(tmp_path: Path) -> None:
    # Valid JSON but missing `planned_values` — this is the shape you get
    # if a user runs `terraform plan -json` (streaming log format) instead
    # of `terraform show -json <plan>`.
    wrong = _write_plan(tmp_path, {"format_version": "1.0", "messages": []})
    with pytest.raises(DetectorError, match="does not look like"):
        parse_plan_json(wrong)


def test_malformed_resource_structure_raises_detector_error(tmp_path: Path) -> None:
    # Missing required field on a resource entry — TerraformPlan pydantic
    # validation should reject.
    bad_plan = {
        "format_version": "1.2",
        "planned_values": {
            "root_module": {
                "resources": [{"address": "x", "mode": "managed"}],  # missing type/name
            }
        },
    }
    wrong = _write_plan(tmp_path, bad_plan)
    with pytest.raises(DetectorError, match="failed to validate plan JSON"):
        parse_plan_json(wrong)
