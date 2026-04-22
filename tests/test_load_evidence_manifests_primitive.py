"""`load_evidence_manifests` primitive tests.

Tests exercise the full path: write manifest YAML fixtures, open a
provenance store, activate it, run the primitive, assert on both the
returned `LoadEvidenceManifestsOutput` and the records actually persisted.
Mirrors the shape of `tests/test_scan_primitive.py`.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from efterlev.primitives.evidence import (
    LoadEvidenceManifestsInput,
    load_evidence_manifests,
)
from efterlev.provenance import ProvenanceStore, active_store

_KSI = "KSI-AFR-FSI"
_KSI_CONTROLS = {_KSI: ["IR-6", "IR-7"]}


def _write_manifest(
    dir_: Path,
    *,
    filename: str = "security-inbox.yml",
    ksi: str = _KSI,
    next_review: str | None = "2027-04-15",
    attestations: int = 1,
) -> Path:
    lines = [f"ksi: {ksi}", "name: Example", "evidence:"]
    for i in range(attestations):
        lines.extend(
            [
                "  - type: attestation",
                f"    statement: Attestation number {i}.",
                "    attested_by: vp-security@example.com",
                "    attested_at: 2026-04-15",
            ]
        )
        if next_review is not None:
            lines.append(f"    next_review: {next_review}")
    path = dir_ / filename
    path.write_text("\n".join(lines) + "\n")
    return path


def test_primitive_of_empty_dir_is_a_clean_noop(tmp_path: Path) -> None:
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = load_evidence_manifests(
            LoadEvidenceManifestsInput(
                manifest_dir=tmp_path / "manifests",
                ksi_to_controls=_KSI_CONTROLS,
            )
        )
    assert result.files_found == 0
    assert result.manifests_loaded == 0
    assert result.evidence == []
    assert result.per_manifest == []


def test_primitive_loads_manifest_and_emits_evidence(tmp_path: Path) -> None:
    manifest_dir = tmp_path / ".efterlev" / "manifests"
    manifest_dir.mkdir(parents=True)
    _write_manifest(manifest_dir)

    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = load_evidence_manifests(
            LoadEvidenceManifestsInput(
                manifest_dir=manifest_dir,
                ksi_to_controls=_KSI_CONTROLS,
            )
        )
        record_ids = store.iter_records()
        evidence_records = store.iter_evidence()

    assert result.files_found == 1
    assert result.manifests_loaded == 1
    assert result.evidence_count == 1
    ev = result.evidence[0]
    assert ev.detector_id == "manifest"
    assert ev.ksis_evidenced == [_KSI]
    assert ev.controls_evidenced == ["IR-6", "IR-7"]
    assert ev.content["statement"] == "Attestation number 0."
    assert ev.content["attested_by"] == "vp-security@example.com"
    assert ev.content["manifest_name"] == "Example"
    assert ev.content["is_stale"] is False

    # One Evidence record + one primitive-invocation record. iter_evidence()
    # returns only the structurally-Evidence payloads; iter_records returns both.
    assert len(evidence_records) == 1
    assert len(record_ids) == 2


def test_primitive_marks_past_due_attestation_as_stale(tmp_path: Path) -> None:
    manifest_dir = tmp_path / ".efterlev" / "manifests"
    manifest_dir.mkdir(parents=True)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    _write_manifest(manifest_dir, next_review=yesterday)

    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = load_evidence_manifests(
            LoadEvidenceManifestsInput(
                manifest_dir=manifest_dir,
                ksi_to_controls=_KSI_CONTROLS,
            )
        )

    assert result.evidence[0].content["is_stale"] is True


def test_primitive_skips_unknown_ksi_and_reports(tmp_path: Path) -> None:
    manifest_dir = tmp_path / ".efterlev" / "manifests"
    manifest_dir.mkdir(parents=True)
    _write_manifest(manifest_dir, ksi="KSI-DOES-NOT-EXIST")

    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = load_evidence_manifests(
            LoadEvidenceManifestsInput(
                manifest_dir=manifest_dir,
                ksi_to_controls=_KSI_CONTROLS,
            )
        )
        evidence_records = store.iter_evidence()

    assert result.files_found == 1
    assert result.manifests_loaded == 0
    assert result.evidence == []
    assert result.skipped_unknown_ksi == ["KSI-DOES-NOT-EXIST"]
    # Nothing Evidence-shaped was persisted for the skipped manifest.
    assert evidence_records == []


def test_primitive_emits_one_evidence_per_attestation(tmp_path: Path) -> None:
    manifest_dir = tmp_path / ".efterlev" / "manifests"
    manifest_dir.mkdir(parents=True)
    _write_manifest(manifest_dir, attestations=3)

    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = load_evidence_manifests(
            LoadEvidenceManifestsInput(
                manifest_dir=manifest_dir,
                ksi_to_controls=_KSI_CONTROLS,
            )
        )
        evidence_records = store.iter_evidence()

    assert result.evidence_count == 3
    assert result.per_manifest[0].attestation_count == 3
    assert len(evidence_records) == 3
    # Each attestation produced a distinct Evidence id (different statements).
    ids = {ev.evidence_id for ev in result.evidence}
    assert len(ids) == 3


def test_primitive_handles_multiple_manifests(tmp_path: Path) -> None:
    manifest_dir = tmp_path / ".efterlev" / "manifests"
    manifest_dir.mkdir(parents=True)
    _write_manifest(manifest_dir, filename="a.yml")
    _write_manifest(manifest_dir, filename="b.yml", attestations=2)

    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = load_evidence_manifests(
            LoadEvidenceManifestsInput(
                manifest_dir=manifest_dir,
                ksi_to_controls=_KSI_CONTROLS,
            )
        )

    assert result.files_found == 2
    assert result.manifests_loaded == 2
    assert result.evidence_count == 3
    assert {m.file.name for m in result.per_manifest} == {"a.yml", "b.yml"}
