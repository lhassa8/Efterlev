"""`scan_terraform` primitive tests.

Tests exercise the full path: write .tf fixtures, open a provenance store,
activate it as the scan's context store, run the primitive, and assert on
both the returned ScanTerraformOutput and the records actually persisted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from efterlev.errors import DetectorError
from efterlev.primitives.scan import ScanTerraformInput, scan_terraform
from efterlev.provenance import ProvenanceStore, active_store


def _write_encrypted_bucket(dir_: Path) -> None:
    (dir_ / "main.tf").write_text(
        'resource "aws_s3_bucket" "audit" {\n'
        '  bucket = "audit-logs"\n'
        "  server_side_encryption_configuration {\n"
        "    rule {\n"
        "      apply_server_side_encryption_by_default {\n"
        '        sse_algorithm = "AES256"\n'
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )


def _write_plain_bucket(dir_: Path) -> None:
    (dir_ / "plain.tf").write_text('resource "aws_s3_bucket" "open" { bucket = "open" }\n')


def _terraform_detector_count() -> int:
    """Count every terraform-sourced detector registered — source of truth."""
    from efterlev.detectors.base import get_registry

    return sum(1 for spec in get_registry().values() if spec.source == "terraform")


def test_scan_of_encrypted_bucket_produces_one_evidence(tmp_path: Path) -> None:
    _write_encrypted_bucket(tmp_path)
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = scan_terraform(ScanTerraformInput(target_dir=tmp_path))
    assert result.resources_parsed == 1
    assert result.detectors_run == _terraform_detector_count()
    # Only the S3-encryption detector produces evidence for an S3 bucket;
    # the others (LB, IAM, CloudTrail, backup) no-op on this input.
    encryption_evidence = [e for e in result.evidence if "encryption_state" in e.content]
    assert len(encryption_evidence) == 1
    ev = encryption_evidence[0]
    assert ev.content["encryption_state"] == "present"
    assert ev.content["algorithm"] == "AES256"


def test_scan_of_plain_bucket_produces_absent_evidence(tmp_path: Path) -> None:
    _write_plain_bucket(tmp_path)
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = scan_terraform(ScanTerraformInput(target_dir=tmp_path))
    encryption_evidence = [e for e in result.evidence if "encryption_state" in e.content]
    assert len(encryption_evidence) == 1
    assert encryption_evidence[0].content["encryption_state"] == "absent"


def test_scan_persists_evidence_and_one_primitive_invocation_record(tmp_path: Path) -> None:
    _write_encrypted_bucket(tmp_path)
    _write_plain_bucket(tmp_path)
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = scan_terraform(ScanTerraformInput(target_dir=tmp_path))
        record_ids = store.iter_records()

    # Two buckets, one encryption-at-rest hit each; other detectors no-op on S3.
    assert result.evidence_count == 2
    # Two detector-emitted Evidence + one scan_terraform invocation record.
    assert len(record_ids) == 3


def test_scan_without_tf_files_is_a_clean_noop(tmp_path: Path) -> None:
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = scan_terraform(ScanTerraformInput(target_dir=tmp_path))
    assert result.resources_parsed == 0
    assert result.detectors_run == _terraform_detector_count()
    assert result.evidence_count == 0


def test_scan_collects_parse_failures_and_continues(tmp_path: Path) -> None:
    """Bad-syntax files no longer abort the scan — they're recorded.

    Pre-2026-04-25 contract: one bad .tf file raised DetectorError and
    aborted the whole scan. New contract: each unparseable file lands in
    `result.parse_failures` and the scan proceeds with the rest. Discovered
    while dogfooding cloudposse/terraform-aws-components (1801 files; the
    abort-on-first behavior made the tool unusable on any real codebase).
    """
    (tmp_path / "bad.tf").write_text("not valid { terraform")
    (tmp_path / "good.tf").write_text(
        'resource "aws_s3_bucket" "ok" { bucket = "ok" }\n'
    )
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = scan_terraform(ScanTerraformInput(target_dir=tmp_path))

    assert result.resources_parsed == 1
    assert len(result.parse_failures) == 1
    assert str(result.parse_failures[0].file) == "bad.tf"
    # Detectors still ran against the file that did parse.
    assert result.detectors_run == _terraform_detector_count()


def test_scan_all_files_unparseable_returns_zero_resources(tmp_path: Path) -> None:
    """If every file fails to parse, the scan still completes.

    The scan primitive is partial-success-by-design; the CLI is the layer
    that decides whether to exit non-zero (it does, when `resources_parsed`
    is 0 AND `parse_failures` is non-empty). Tested separately at the CLI
    layer, not here.
    """
    (tmp_path / "bad1.tf").write_text("invalid { syntax")
    (tmp_path / "bad2.tf").write_text("also { invalid")
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = scan_terraform(ScanTerraformInput(target_dir=tmp_path))
    assert result.resources_parsed == 0
    assert {str(f.file) for f in result.parse_failures} == {"bad1.tf", "bad2.tf"}


def test_scan_nonexistent_target_raises(tmp_path: Path) -> None:
    with (
        ProvenanceStore(tmp_path) as store,
        active_store(store),
        pytest.raises(DetectorError, match="not a directory"),
    ):
        scan_terraform(ScanTerraformInput(target_dir=tmp_path / "no-such-dir"))
