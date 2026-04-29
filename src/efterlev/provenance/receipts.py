"""JSONL append-only receipt log for the provenance store.

One line per `write_record` call. The log is an independent sidechannel to the
SQLite store: a `verify_receipts` walk cross-checks the two to surface any
tampering that content-addressing alone can't catch (consistent rewrites of
both the SQLite DB and the blob store would pass hash verification but leave
the receipt log visibly out of sync).

Atomicity: each append opens the file in `O_APPEND` mode, takes an exclusive
`fcntl.flock`, writes a single JSON line + newline, and fsyncs. POSIX-only
(macOS + Linux); Windows support is on the v1.5+ roadmap.

Per-line schema (stable):

    {
      "ts":            ISO-8601 string,
      "record_id":     "sha256:...",
      "record_type":   one of evidence|claim|finding|mapping|remediation,
      "derived_from":  ["sha256:...", ...],
      "primitive":     "name@version" | null,
      "agent":         "name" | null,
      "model":         "model-id" | null,
      "prompt_hash":   "sha256:..." | null
    }

Per DECISIONS 2026-04-20 (design call #5): full `derived_from` list is stored
inline rather than hashed so a reader can reconstruct chain topology from the
log alone if the SQLite store is lost or suspect.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any

from efterlev.errors import ProvenanceError
from efterlev.models import ProvenanceRecord


class ReceiptLog:
    """Append-only JSONL record of every write to the provenance store."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Create the file if missing so flock has something to acquire.
        self.path.touch(exist_ok=True)

    def append(self, record: ProvenanceRecord) -> None:
        line = json.dumps(
            {
                "ts": record.timestamp.isoformat(),
                "record_id": record.record_id,
                "record_type": record.record_type,
                "derived_from": list(record.derived_from),
                "primitive": record.primitive,
                "agent": record.agent,
                "model": record.model,
                "prompt_hash": record.prompt_hash,
            },
            separators=(",", ":"),
        )
        data = (line + "\n").encode("utf-8")

        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                os.write(fd, data)
                os.fsync(fd)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def read_all(self) -> list[dict[str, Any]]:
        """Parse every line; raise ProvenanceError on a malformed line."""
        if not self.path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for lineno, raw in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                entries.append(json.loads(raw))
            except json.JSONDecodeError as e:
                raise ProvenanceError(f"receipts.log line {lineno} is not valid JSON: {e}") from e
        return entries
