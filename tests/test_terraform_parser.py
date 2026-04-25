"""Terraform parser tests — per-file parsing, tree walking, nested-block access.

Every test writes its own `.tf` source into `tmp_path` so fixtures are visible
in-test and no shared state exists between tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from efterlev.errors import DetectorError
from efterlev.terraform import parse_terraform_file, parse_terraform_tree


def test_parses_single_bucket_resource(tmp_path: Path) -> None:
    tf = tmp_path / "main.tf"
    tf.write_text('resource "aws_s3_bucket" "logs" {\n  bucket = "my-logs"\n}\n')
    resources = parse_terraform_file(tf)
    assert len(resources) == 1
    r = resources[0]
    assert r.type == "aws_s3_bucket"
    assert r.name == "logs"
    assert r.body.get("bucket") == "my-logs"
    # Single-file caller with no repo-root context → path recorded verbatim.
    assert r.source_ref.file == tf
    assert r.source_ref.line_start == 1
    assert r.source_ref.line_end is not None
    assert r.source_ref.line_end >= 2


def test_parse_tree_records_paths_relative_to_target_dir(tmp_path: Path) -> None:
    """`source_ref.file` must be repo-relative when walked via parse_terraform_tree.

    Keeps the provenance store, HTML reports, and FRMR JSON output free
    of the user's absolute filesystem layout. Readers recover the
    absolute path via `paths.resolve_within_root(file, root)`.
    """
    nested = tmp_path / "infra" / "modules"
    nested.mkdir(parents=True)
    (nested / "bucket.tf").write_text('resource "aws_s3_bucket" "a" { bucket = "a" }\n')
    (tmp_path / "root.tf").write_text('resource "aws_s3_bucket" "b" { bucket = "b" }\n')

    result = parse_terraform_tree(tmp_path)
    recorded = {str(r.source_ref.file) for r in result.resources}
    # Both paths are relative to tmp_path (never absolute, never containing
    # the test's /tmp/pytest-of-*/… prefix).
    assert recorded == {"root.tf", "infra/modules/bucket.tf"}
    for r in result.resources:
        assert not r.source_ref.file.is_absolute()
    assert result.parse_failures == []


def test_parse_file_with_explicit_record_as_uses_that_path(tmp_path: Path) -> None:
    tf = tmp_path / "main.tf"
    tf.write_text('resource "aws_s3_bucket" "logs" { bucket = "l" }\n')
    resources = parse_terraform_file(tf, record_as=Path("infra/main.tf"))
    assert str(resources[0].source_ref.file) == "infra/main.tf"


def test_parses_multiple_resources_with_distinct_line_ranges(tmp_path: Path) -> None:
    tf = tmp_path / "main.tf"
    tf.write_text(
        'resource "aws_s3_bucket" "a" {\n'
        '  bucket = "a"\n'
        "}\n"
        "\n"
        'resource "aws_s3_bucket" "b" {\n'
        '  bucket = "b"\n'
        "}\n"
    )
    resources = parse_terraform_file(tf)
    assert len(resources) == 2
    by_name = {r.name: r for r in resources}
    assert by_name["a"].source_ref.line_start == 1
    assert by_name["b"].source_ref.line_start == 5


def test_nested_blocks_accessible_via_get_nested(tmp_path: Path) -> None:
    tf = tmp_path / "main.tf"
    tf.write_text(
        'resource "aws_s3_bucket" "encrypted" {\n'
        '  bucket = "enc"\n'
        "  server_side_encryption_configuration {\n"
        "    rule {\n"
        "      apply_server_side_encryption_by_default {\n"
        '        sse_algorithm = "AES256"\n'
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    [r] = parse_terraform_file(tf)
    sse = r.get_nested(
        "server_side_encryption_configuration",
        "rule",
        "apply_server_side_encryption_by_default",
    )
    assert sse == {"sse_algorithm": "AES256"}


def test_ignores_non_resource_blocks(tmp_path: Path) -> None:
    tf = tmp_path / "main.tf"
    tf.write_text(
        'variable "region" { default = "us-east-1" }\n'
        "\n"
        'data "aws_caller_identity" "current" {}\n'
        "\n"
        'resource "aws_s3_bucket" "logs" {\n'
        '  bucket = "my-logs"\n'
        "}\n"
    )
    resources = parse_terraform_file(tf)
    assert len(resources) == 1
    assert resources[0].type == "aws_s3_bucket"


def test_walks_tree_across_subdirectories(tmp_path: Path) -> None:
    (tmp_path / "main.tf").write_text('resource "aws_s3_bucket" "main" { bucket = "main" }\n')
    (tmp_path / "modules").mkdir()
    (tmp_path / "modules" / "sub.tf").write_text(
        'resource "aws_s3_bucket" "sub" { bucket = "sub" }\n'
    )
    # Non-.tf files are ignored.
    (tmp_path / "README.md").write_text("# not terraform")

    result = parse_terraform_tree(tmp_path)
    assert {r.name for r in result.resources} == {"main", "sub"}
    assert result.parse_failures == []


def test_bad_syntax_raises_detector_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tf"
    bad.write_text("this is not { valid terraform")
    with pytest.raises(DetectorError, match="failed to parse"):
        parse_terraform_file(bad)


def test_nonexistent_target_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(DetectorError, match="not a directory"):
        parse_terraform_tree(tmp_path / "no-such-dir")


def test_empty_dir_returns_empty_result(tmp_path: Path) -> None:
    result = parse_terraform_tree(tmp_path)
    assert result.resources == []
    assert result.parse_failures == []


def test_tree_walk_collects_failures_and_continues(tmp_path: Path) -> None:
    """Real-world contract: one bad file does NOT abort the whole walk.

    Discovered 2026-04-25 dogfooding cloudposse/terraform-aws-components
    (1801 .tf files): the legacy abort-on-first-failure behavior made the
    tool unusable on any real codebase, since python-hcl2 lags upstream
    Terraform syntax. Collect-and-continue is the launch-blocker fix.
    """
    (tmp_path / "good.tf").write_text(
        'resource "aws_s3_bucket" "ok" { bucket = "ok" }\n'
    )
    (tmp_path / "bad.tf").write_text("this is not { valid terraform")
    (tmp_path / "also_good.tf").write_text(
        'resource "aws_s3_bucket" "ok2" { bucket = "ok2" }\n'
    )

    result = parse_terraform_tree(tmp_path)

    # Good files parsed; bad file collected as a failure record (not raised).
    assert {r.name for r in result.resources} == {"ok", "ok2"}
    assert len(result.parse_failures) == 1
    failure = result.parse_failures[0]
    assert str(failure.file) == "bad.tf"
    # The relative-path-clean reason should NOT include the absolute path
    # prefix — repo-relative is the rendering contract, same as resources.
    assert str(tmp_path) not in failure.reason
    assert failure.reason  # non-empty


def test_tree_walk_all_files_fail_returns_empty_resources(tmp_path: Path) -> None:
    (tmp_path / "bad1.tf").write_text("this is { not valid")
    (tmp_path / "bad2.tf").write_text("also { not valid")

    result = parse_terraform_tree(tmp_path)
    assert result.resources == []
    assert {str(f.file) for f in result.parse_failures} == {"bad1.tf", "bad2.tf"}


def test_get_nested_returns_none_on_missing_path(tmp_path: Path) -> None:
    tf = tmp_path / "main.tf"
    tf.write_text('resource "aws_s3_bucket" "plain" { bucket = "p" }\n')
    [r] = parse_terraform_file(tf)
    assert r.get_nested("does", "not", "exist") is None
