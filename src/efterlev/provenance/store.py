"""Local, append-only, content-addressed provenance store.

Two on-disk components under `.efterlev/`:

  store.db       SQLite — one row per `ProvenanceRecord`
  store/xx/yy/…  content-addressed blob store — raw payloads (Evidence / Claim
                 content dicts serialized as JSON) at paths derived from their
                 own SHA-256

The blob store is write-idempotent: same payload → same path → second write
is a no-op. Records referencing identical payloads share a blob; the records
themselves differ because a `ProvenanceRecord` carries its own timestamp and
origin metadata, so two writes of the same payload at different times produce
two distinct records pointing at the same blob. This is the right semantic for
"new evidence for the same thing at a later date" without overwriting history.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from efterlev.errors import ProvenanceError
from efterlev.models import ProvenanceRecord, RecordType
from efterlev.provenance.receipts import ReceiptLog

_SCHEMA = """
CREATE TABLE IF NOT EXISTS provenance_records (
    record_id    TEXT PRIMARY KEY,
    record_type  TEXT NOT NULL,
    content_ref  TEXT NOT NULL,
    derived_from TEXT NOT NULL,
    primitive    TEXT,
    agent        TEXT,
    model        TEXT,
    prompt_hash  TEXT,
    timestamp    TEXT NOT NULL,
    metadata     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_record_type ON provenance_records(record_type);
CREATE INDEX IF NOT EXISTS idx_timestamp   ON provenance_records(timestamp);
"""


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _shard_path(payload_hash: str) -> Path:
    # e.g. "abcd1234..." -> Path("ab/cd/abcd1234...")
    return Path(payload_hash[:2]) / payload_hash[2:4] / payload_hash


class ProvenanceStore:
    """SQLite-backed record index plus content-addressed blob store.

    All paths under `root / ".efterlev"`; the constructor creates the directory
    tree and schema on first use, so it is safe to point at either an existing
    store or a fresh directory.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.efterlev_dir = self.root / ".efterlev"
        self.db_path = self.efterlev_dir / "store.db"
        self.blob_dir = self.efterlev_dir / "store"
        self.receipts = ReceiptLog(self.efterlev_dir / "receipts.log")

        self.efterlev_dir.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        # `check_same_thread=False` lets the same ProvenanceStore instance be
        # used from multiple threads (e.g., a parallel scan). SQLite's file-
        # level locking handles concurrency at the DB layer; `_write_lock`
        # serializes our Python-side use of the connection object itself.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._write_lock = threading.Lock()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ProvenanceStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- writes ---------------------------------------------------------------

    def write_record(
        self,
        *,
        payload: dict[str, Any],
        record_type: RecordType,
        derived_from: list[str] | None = None,
        primitive: str | None = None,
        agent: str | None = None,
        model: str | None = None,
        prompt_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProvenanceRecord:
        """Persist `payload` to the blob store and insert a ProvenanceRecord row.

        Atomically appends a receipt log line. Returns the finalized record (with
        its content-addressed `record_id` computed).
        """
        content_ref = self._put_blob(payload)
        record = ProvenanceRecord.create(
            record_type=record_type,
            content_ref=content_ref,
            derived_from=derived_from,
            primitive=primitive,
            agent=agent,
            model=model,
            prompt_hash=prompt_hash,
            metadata=metadata,
        )

        with self._write_lock:
            try:
                self._conn.execute(
                    "INSERT OR IGNORE INTO provenance_records "
                    "(record_id, record_type, content_ref, derived_from, "
                    " primitive, agent, model, prompt_hash, timestamp, metadata) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record.record_id,
                        record.record_type,
                        record.content_ref,
                        json.dumps(record.derived_from),
                        record.primitive,
                        record.agent,
                        record.model,
                        record.prompt_hash,
                        record.timestamp.isoformat(),
                        json.dumps(record.metadata),
                    ),
                )
                self._conn.commit()
            except sqlite3.Error as e:
                raise ProvenanceError(f"failed to insert record {record.record_id}: {e}") from e

        self.receipts.append(record)
        return record

    def _put_blob(self, payload: dict[str, Any]) -> str:
        """Write payload to blob store (idempotent); return relative content_ref."""
        data = _canonical_bytes(payload)
        digest = hashlib.sha256(data).hexdigest()
        rel = _shard_path(digest)
        full = self.blob_dir / rel.with_suffix(".json")
        if not full.exists():
            full.parent.mkdir(parents=True, exist_ok=True)
            # Write with a tmp+rename so partial writes never leave a half-file
            # that a later read would treat as valid.
            tmp = full.with_suffix(".json.tmp")
            tmp.write_bytes(data)
            tmp.rename(full)
        return str(rel.with_suffix(".json"))

    # --- reads ----------------------------------------------------------------

    def get_record(self, record_id: str) -> ProvenanceRecord | None:
        row = self._conn.execute(
            "SELECT record_type, content_ref, derived_from, primitive, agent, "
            "model, prompt_hash, timestamp, metadata "
            "FROM provenance_records WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            return None
        (
            record_type,
            content_ref,
            derived_from,
            primitive,
            agent,
            model,
            prompt_hash,
            timestamp,
            metadata,
        ) = row
        return ProvenanceRecord(
            record_id=record_id,
            record_type=record_type,
            content_ref=content_ref,
            derived_from=json.loads(derived_from),
            primitive=primitive,
            agent=agent,
            model=model,
            prompt_hash=prompt_hash,
            timestamp=timestamp,  # pydantic coerces ISO str to datetime
            metadata=json.loads(metadata),
        )

    def read_payload(self, record: ProvenanceRecord) -> dict[str, Any]:
        full = self.blob_dir / record.content_ref
        if not full.exists():
            raise ProvenanceError(
                f"blob missing for record {record.record_id}: {record.content_ref}"
            )
        try:
            data: dict[str, Any] = json.loads(full.read_bytes())
        except json.JSONDecodeError as e:
            raise ProvenanceError(f"blob at {record.content_ref} is not valid JSON: {e}") from e
        return data

    def iter_records(self) -> list[str]:
        """Return every record_id in insertion order (by timestamp)."""
        rows = self._conn.execute(
            "SELECT record_id FROM provenance_records ORDER BY timestamp, record_id"
        ).fetchall()
        return [r[0] for r in rows]

    def iter_evidence(self) -> list[tuple[str, dict[str, Any]]]:
        """Return `(record_id, evidence_payload)` for every detector-emitted record.

        Filters on `record_type="evidence"` + payload that parses as an
        Evidence model dump (checked structurally via required keys). Primitive
        invocation records share record_type="evidence" when the primitive is
        deterministic but have payload shape `{"input": ..., "output": ...}`,
        so the structural filter cleanly separates them.

        Returns a list because iteration order matters for deterministic
        display and test assertions; the list size is bounded by the number
        of detector hits, which at v0 is small.
        """
        rows = self._conn.execute(
            "SELECT record_id, content_ref FROM provenance_records "
            "WHERE record_type = 'evidence' ORDER BY timestamp, record_id"
        ).fetchall()
        results: list[tuple[str, dict[str, Any]]] = []
        for record_id, content_ref in rows:
            full = self.blob_dir / content_ref
            if not full.exists():
                continue
            try:
                payload = json.loads(full.read_bytes())
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            # Detector-emitted Evidence has these required fields; primitive
            # invocation records have {"input","output"} instead.
            if {"detector_id", "source_ref", "timestamp"} <= payload.keys():
                results.append((record_id, payload))
        return results

    def iter_claims_by_metadata_kind(
        self, kind: str
    ) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
        """Return `(record_id, metadata, payload)` for every claim tagged `kind`.

        The Gap Agent tags each KSI classification Claim with
        `metadata={"kind": "ksi_classification", ...}`. Downstream agents
        (Documentation, Remediation) find the classifications by filtering on
        the kind tag rather than re-classifying from raw evidence.

        The filter is `record_type="claim"` + `metadata.kind=<kind>`; payloads
        are returned alongside so callers can reconstruct the Claim content
        without a second blob read.
        """
        rows = self._conn.execute(
            "SELECT record_id, metadata, content_ref FROM provenance_records "
            "WHERE record_type = 'claim' ORDER BY timestamp, record_id"
        ).fetchall()
        results: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for record_id, metadata_json, content_ref in rows:
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                continue
            if not isinstance(metadata, dict) or metadata.get("kind") != kind:
                continue
            full = self.blob_dir / content_ref
            if not full.exists():
                continue
            try:
                payload = json.loads(full.read_bytes())
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                results.append((record_id, metadata, payload))
        return results
