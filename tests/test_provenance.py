"""Provenance store, receipt log, walker, and verify tests.

Uses `tmp_path` for filesystem isolation — every test gets a fresh
`.efterlev/` under a pytest-managed temp dir. The store and receipts log
are both on disk, so these are integration-ish tests, not pure units.
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Thread

import pytest

from efterlev.errors import ProvenanceError
from efterlev.provenance import (
    ProvenanceStore,
    render_chain_text,
    verify_receipts,
    walk_chain,
)

# --- ProvenanceStore: writes and reads ----------------------------------------


def test_store_write_then_get_record(tmp_path: Path) -> None:
    with ProvenanceStore(tmp_path) as store:
        record = store.write_record(
            payload={"detector_id": "aws.test", "content": {"x": 1}},
            record_type="evidence",
            primitive="scan_terraform@0.1.0",
        )
        assert record.record_id.startswith("sha256:")
        assert record.content_ref.endswith(".json")

        roundtrip = store.get_record(record.record_id)
        assert roundtrip is not None
        assert roundtrip.record_id == record.record_id
        assert roundtrip.record_type == "evidence"
        assert roundtrip.primitive == "scan_terraform@0.1.0"


def test_store_read_payload_round_trips_original_dict(tmp_path: Path) -> None:
    payload = {"detector_id": "aws.test", "content": {"resource": "bucket-1", "ok": True}}
    with ProvenanceStore(tmp_path) as store:
        record = store.write_record(payload=payload, record_type="evidence")
        assert store.read_payload(record) == payload


def test_store_same_payload_twice_shares_blob_but_produces_distinct_records(
    tmp_path: Path,
) -> None:
    payload = {"detector_id": "aws.test", "content": {"x": 1}}
    with ProvenanceStore(tmp_path) as store:
        first = store.write_record(payload=payload, record_type="evidence")
        second = store.write_record(payload=payload, record_type="evidence")
        # Different records because timestamps differ...
        assert first.record_id != second.record_id
        # ...but the same blob on disk.
        assert first.content_ref == second.content_ref


def test_store_missing_record_returns_none(tmp_path: Path) -> None:
    with ProvenanceStore(tmp_path) as store:
        assert store.get_record("sha256:" + "0" * 64) is None


def test_store_read_payload_raises_when_blob_missing(tmp_path: Path) -> None:
    with ProvenanceStore(tmp_path) as store:
        record = store.write_record(payload={"detector_id": "a"}, record_type="evidence")
        # Simulate a corrupted store by deleting the blob.
        (store.blob_dir / record.content_ref).unlink()
        with pytest.raises(ProvenanceError, match="blob missing"):
            store.read_payload(record)


# --- ReceiptLog: atomicity under concurrency ----------------------------------


def test_receipt_log_written_per_record(tmp_path: Path) -> None:
    with ProvenanceStore(tmp_path) as store:
        store.write_record(payload={"a": 1}, record_type="evidence")
        store.write_record(payload={"a": 2}, record_type="evidence")
        entries = store.receipts.read_all()
        assert len(entries) == 2
        assert all(e["record_id"].startswith("sha256:") for e in entries)


def test_receipt_log_survives_concurrent_writes(tmp_path: Path) -> None:
    # Ten threads each write three records in parallel. Expect 30 receipt
    # lines total, every line valid JSON (flock serializes writes).
    store = ProvenanceStore(tmp_path)

    def worker(i: int) -> None:
        for j in range(3):
            store.write_record(payload={"worker": i, "n": j}, record_type="evidence")

    threads = [Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    entries = store.receipts.read_all()
    assert len(entries) == 30
    # No duplicated record_ids (thread uniqueness via worker+n tuple in payload).
    assert len({e["record_id"] for e in entries}) == 30
    store.close()


# --- Walker -------------------------------------------------------------------


def test_walker_walks_three_node_chain(tmp_path: Path) -> None:
    # evidence  <--  claim1  <--  claim2
    with ProvenanceStore(tmp_path) as store:
        ev = store.write_record(
            payload={"source": "main.tf"},
            record_type="evidence",
            primitive="scan_terraform@0.1.0",
        )
        c1 = store.write_record(
            payload={"kind": "intermediate"},
            record_type="claim",
            derived_from=[ev.record_id],
            agent="gap_agent",
            model="claude-opus-4-7",
        )
        c2 = store.write_record(
            payload={"kind": "leaf"},
            record_type="claim",
            derived_from=[c1.record_id],
            agent="documentation_agent",
            model="claude-opus-4-7",
        )

        tree = walk_chain(store, c2.record_id)
        assert tree.record.record_id == c2.record_id
        assert len(tree.parents) == 1
        assert tree.parents[0].record.record_id == c1.record_id
        assert len(tree.parents[0].parents) == 1
        assert tree.parents[0].parents[0].record.record_id == ev.record_id
        assert tree.parents[0].parents[0].parents == []  # leaf


def test_walker_raises_on_missing_record(tmp_path: Path) -> None:
    with (
        ProvenanceStore(tmp_path) as store,
        pytest.raises(ProvenanceError, match="record not found"),
    ):
        walk_chain(store, "sha256:" + "0" * 64)


def test_walker_resolves_evidence_id_via_dual_key_lookup(tmp_path: Path) -> None:
    """`provenance show <evidence_id>` must work, not just `<record_id>`.

    Discovered 2026-04-25 in the round-1 3PAO review of a real attestation
    artifact: the artifact's `citations[].evidence_id` (Evidence content
    hash) was not the same as the wrapping `ProvenanceRecord.record_id`
    (envelope hash including timestamps + metadata). The store-level
    validator did dual-key lookup (`_validate_claim_derived_from`); the
    walker did not. Result: every cited evidence_id failed
    `provenance show`, blocking traceability.

    This test locks the dual-key contract on the walker. Walking by
    evidence_id must produce the same result as walking by record_id.
    """
    with ProvenanceStore(tmp_path) as store:
        # Write an evidence record carrying its own `evidence_id` field
        # in the payload — mirrors the real Evidence shape produced by
        # detectors. The Evidence's evidence_id is intentionally distinct
        # from the wrapping ProvenanceRecord's record_id.
        evidence_payload = {
            "evidence_id": "sha256:" + "a" * 64,  # the content hash
            "detector_id": "aws.test",
            "content": {"resource_name": "bucket-1"},
        }
        record = store.write_record(
            payload=evidence_payload,
            record_type="evidence",
            primitive="scan_terraform@0.1.0",
        )
        # Confirm the two ids genuinely differ (precondition for the
        # bug class — if they're ever the same, this test is moot).
        assert record.record_id != evidence_payload["evidence_id"]

        # Walk by record_id — works historically.
        by_record = walk_chain(store, record.record_id)
        assert by_record.record.record_id == record.record_id

        # Walk by evidence_id — must work post-fix.
        by_evidence = walk_chain(store, evidence_payload["evidence_id"])
        assert by_evidence.record.record_id == record.record_id


def test_resolve_to_record_returns_none_on_unresolvable_id(tmp_path: Path) -> None:
    """Helper contract: misses return None, not raise.

    `walk_chain` is responsible for raising `ProvenanceError` on miss
    (with chain context). The resolver itself returns None — keeps
    error semantics out of the lookup helper.
    """
    with ProvenanceStore(tmp_path) as store:
        store.write_record(
            payload={"evidence_id": "sha256:" + "b" * 64, "x": 1},
            record_type="evidence",
        )
        assert store.resolve_to_record("sha256:" + "0" * 64) is None


def test_walker_raises_on_cycle(tmp_path: Path) -> None:
    # Manufacture a corrupt store by writing a record whose derived_from
    # references itself via direct SQL. Walker must detect the cycle.
    with ProvenanceStore(tmp_path) as store:
        record = store.write_record(payload={"x": 1}, record_type="evidence")
        store._conn.execute(
            "UPDATE provenance_records SET derived_from = ? WHERE record_id = ?",
            (json.dumps([record.record_id]), record.record_id),
        )
        store._conn.commit()

        with pytest.raises(ProvenanceError, match="cycle in provenance graph"):
            walk_chain(store, record.record_id)


def test_render_chain_text_indents_parents(tmp_path: Path) -> None:
    with ProvenanceStore(tmp_path) as store:
        ev = store.write_record(payload={"x": 1}, record_type="evidence")
        claim = store.write_record(
            payload={"y": 2},
            record_type="claim",
            derived_from=[ev.record_id],
            agent="gap_agent",
            model="claude-opus-4-7",
        )
        tree = walk_chain(store, claim.record_id)
        output = render_chain_text(tree)
        assert claim.record_id in output
        assert ev.record_id in output
        assert "└── " in output  # child marker rendered
        assert "(leaf — no derived_from)" in output


def test_render_chain_text_surfaces_source_ref_at_evidence_leaves(tmp_path: Path) -> None:
    """`efterlev provenance show` must surface source file + line range at
    evidence leaves so the user can trace a claim back to Terraform without
    opening the blob manually. Regression test for the gap caught in the
    2026-04-23 external review."""
    with ProvenanceStore(tmp_path) as store:
        ev = store.write_record(
            payload={
                "detector_id": "aws.encryption_s3_at_rest",
                "source_ref": {"file": "infra/main.tf", "line_start": 12, "line_end": 18},
                "content": {"resource_name": "reports", "encryption_state": "absent"},
            },
            record_type="evidence",
            primitive="aws.encryption_s3_at_rest@0.1.0",
        )
        claim = store.write_record(
            payload={"status": "not_implemented"},
            record_type="claim",
            derived_from=[ev.record_id],
            agent="gap_agent",
            model="claude-opus-4-7",
        )
        tree = walk_chain(store, claim.record_id)
        output = render_chain_text(tree)
        assert "source=infra/main.tf:12-18" in output


def test_render_chain_text_handles_single_line_source_ref(tmp_path: Path) -> None:
    with ProvenanceStore(tmp_path) as store:
        ev = store.write_record(
            payload={
                "source_ref": {"file": "main.tf", "line_start": 5, "line_end": 5},
            },
            record_type="evidence",
        )
        tree = walk_chain(store, ev.record_id)
        output = render_chain_text(tree)
        # Collapse file:5-5 into file:5 for single-line references.
        assert "source=main.tf:5" in output
        assert "5-5" not in output


def test_render_chain_text_omits_source_line_when_payload_lacks_source_ref(
    tmp_path: Path,
) -> None:
    """Non-Evidence records emitted under record_type=evidence by a
    primitive (e.g. init's catalog-loaded receipt) may not have a
    source_ref. The renderer must not crash and must not invent content."""
    with ProvenanceStore(tmp_path) as store:
        rec = store.write_record(
            payload={"action": "catalogs_loaded", "baseline": "fedramp-20x-moderate"},
            record_type="evidence",
            primitive="efterlev.init@0.1.0",
        )
        tree = walk_chain(store, rec.record_id)
        output = render_chain_text(tree)
        assert "source=" not in output


# --- verify_receipts ----------------------------------------------------------


def test_verify_receipts_clean_store(tmp_path: Path) -> None:
    with ProvenanceStore(tmp_path) as store:
        store.write_record(payload={"a": 1}, record_type="evidence")
        store.write_record(payload={"a": 2}, record_type="evidence")
        report = verify_receipts(store)
        assert report.clean
        assert report.store_records == 2
        assert report.receipts == 2
        assert report.missing_receipts == []
        assert report.orphan_receipts == []
        assert report.mismatched == []


def test_verify_receipts_detects_record_without_receipt(tmp_path: Path) -> None:
    # Write one record, then write a second directly to SQLite (bypassing the
    # receipt log) to simulate a tampered store.
    store = ProvenanceStore(tmp_path)
    store.write_record(payload={"a": 1}, record_type="evidence")

    store._conn.execute(
        "INSERT INTO provenance_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "sha256:" + "f" * 64,
            "evidence",
            "ff/ff/ffff.json",
            "[]",
            None,
            None,
            None,
            None,
            "2026-04-20T00:00:00+00:00",
            "{}",
        ),
    )
    store._conn.commit()

    report = verify_receipts(store)
    assert not report.clean
    assert "sha256:" + "f" * 64 in report.missing_receipts
    store.close()


def test_verify_receipts_detects_orphan_receipt(tmp_path: Path) -> None:
    # Write a legit record, then manually append a stray receipt whose
    # record_id isn't in the store.
    store = ProvenanceStore(tmp_path)
    store.write_record(payload={"a": 1}, record_type="evidence")

    stray = {
        "ts": "2026-04-20T00:00:00+00:00",
        "record_id": "sha256:" + "1" * 64,
        "record_type": "evidence",
        "derived_from": [],
        "primitive": None,
        "agent": None,
        "model": None,
        "prompt_hash": None,
    }
    with open(store.receipts.path, "a", encoding="utf-8") as f:
        f.write(json.dumps(stray) + "\n")

    report = verify_receipts(store)
    assert not report.clean
    assert "sha256:" + "1" * 64 in report.orphan_receipts
    store.close()
