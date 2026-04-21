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


def test_scan_of_encrypted_bucket_produces_one_evidence(tmp_path: Path) -> None:
    _write_encrypted_bucket(tmp_path)
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = scan_terraform(ScanTerraformInput(target_dir=tmp_path))
    assert result.resources_parsed == 1
    assert result.detectors_run == 1  # just aws.encryption_s3_at_rest at v0
    assert result.evidence_count == 1
    ev = result.evidence[0]
    assert ev.content["encryption_state"] == "present"
    assert ev.content["algorithm"] == "AES256"


def test_scan_of_plain_bucket_produces_absent_evidence(tmp_path: Path) -> None:
    _write_plain_bucket(tmp_path)
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = scan_terraform(ScanTerraformInput(target_dir=tmp_path))
    assert result.evidence_count == 1
    assert result.evidence[0].content["encryption_state"] == "absent"


def test_scan_persists_evidence_and_one_primitive_invocation_record(tmp_path: Path) -> None:
    _write_encrypted_bucket(tmp_path)
    _write_plain_bucket(tmp_path)
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = scan_terraform(ScanTerraformInput(target_dir=tmp_path))
        record_ids = store.iter_records()

    assert result.evidence_count == 2
    # Two detector-emitted Evidence + one scan_terraform invocation record.
    assert len(record_ids) == 3


def test_scan_without_tf_files_is_a_clean_noop(tmp_path: Path) -> None:
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = scan_terraform(ScanTerraformInput(target_dir=tmp_path))
    assert result.resources_parsed == 0
    assert result.detectors_run == 1
    assert result.evidence_count == 0


def test_scan_bad_syntax_raises_detector_error(tmp_path: Path) -> None:
    (tmp_path / "bad.tf").write_text("not valid { terraform")
    with (
        ProvenanceStore(tmp_path) as store,
        active_store(store),
        pytest.raises(DetectorError, match="failed to parse"),
    ):
        scan_terraform(ScanTerraformInput(target_dir=tmp_path))


def test_scan_nonexistent_target_raises(tmp_path: Path) -> None:
    with (
        ProvenanceStore(tmp_path) as store,
        active_store(store),
        pytest.raises(DetectorError, match="not a directory"),
    ):
        scan_terraform(ScanTerraformInput(target_dir=tmp_path / "no-such-dir"))
