"""Recursive chain walker for the provenance graph.

Given a record_id, follows `derived_from` edges back to the leaves (records
with no parents) and returns a tree the CLI can pretty-print. Cycle detection
exists as a defence against corrupted stores — the graph should be a DAG by
construction, but we don't trust blindly.

For `record_type="evidence"` leaves the walker also loads the stored blob
payload so the text renderer can surface the original `source_ref.file`
and line range — the point of the provenance demo is to trace a generated
claim back to the Terraform file and line that produced the evidence, so
the source location must be visible without the user opening a blob
manually. That functional gap was closed 2026-04-23 after the external
review caught it; see `LIMITATIONS.md` for the prior state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from efterlev.errors import ProvenanceError
from efterlev.models import ProvenanceRecord
from efterlev.provenance.store import ProvenanceStore


@dataclass
class ChainNode:
    """One node in a walked chain, plus its resolved parents.

    `payload` is the deserialized blob contents for evidence records
    only — the walker loads it at walk time so the text renderer can
    surface `source_ref.file:line_start-line_end`. Kept `None` for
    claim / other record types to avoid loading blobs we don't need.
    """

    record: ProvenanceRecord
    parents: list[ChainNode] = field(default_factory=list)
    payload: dict[str, Any] | None = None


def walk_chain(store: ProvenanceStore, record_id: str) -> ChainNode:
    """Resolve the record and its full ancestor tree.

    Raises ProvenanceError if the requested record is missing or if the graph
    contains a cycle (the latter implies store corruption — the record_id
    comes from content hashing, so cycles are structurally impossible in a
    correctly-populated store).
    """
    visiting: set[str] = set()

    def _walk(rid: str) -> ChainNode:
        if rid in visiting:
            raise ProvenanceError(f"cycle in provenance graph at {rid}")
        # Dual-key resolve: a cited id may be either a record_id (envelope
        # hash) or an Evidence.evidence_id (content hash). Agents cite the
        # latter because that's the fence id the model sees; the store
        # indexes the former. The 3PAO review of 2026-04-25 found this
        # asymmetry blocked traceability — `provenance show <evidence_id>`
        # returned "record not found" even though the validator accepted
        # the citation at write time. `resolve_to_record` mirrors the
        # validator's dual-key lookup.
        record = store.resolve_to_record(rid)
        if record is None:
            raise ProvenanceError(f"record not found: {rid}")
        visiting.add(rid)
        try:
            parents = [_walk(parent_id) for parent_id in record.derived_from]
        finally:
            visiting.discard(rid)

        # Load the evidence payload so the renderer has source_ref to
        # display at leaves. A missing / unreadable blob isn't fatal to
        # the walk — we log None and let render_chain_text fall back to
        # `content_ref=<path>`. That keeps `provenance show` useful on
        # a partially-corrupted store.
        payload: dict[str, Any] | None = None
        if record.record_type == "evidence":
            try:
                payload = store.read_payload(record)
            except ProvenanceError:
                payload = None

        return ChainNode(record=record, parents=parents, payload=payload)

    return _walk(record_id)


def render_chain_text(root: ChainNode, indent: int = 0) -> str:
    """Render a chain as an indented ASCII tree for terminal output."""
    prefix = "  " * indent
    r = root.record
    origin = (
        f"primitive={r.primitive}"
        if r.primitive
        else f"agent={r.agent}"
        if r.agent
        else "origin=unknown"
    )
    if r.model:
        origin += f" model={r.model}"
    head = f"{prefix}{'└── ' if indent else ''}{r.record_id}  ({r.record_type})"
    meta = f"{prefix}    {origin}  at {r.timestamp.isoformat()}"
    body = f"{prefix}    content_ref={r.content_ref}"

    out = [head, meta, body]

    # For evidence records, surface the original source location so the
    # user reading a walked chain can see "this record came from
    # main.tf:12-18" without opening the JSON blob. The whole point of
    # the provenance demo rests on this line being here.
    source_line = _format_source_ref(root.payload)
    if source_line is not None:
        out.append(f"{prefix}    source={source_line}")

    if not root.parents:
        out.append(f"{prefix}    (leaf — no derived_from)")
    else:
        for parent in root.parents:
            out.append(render_chain_text(parent, indent + 1))
    return "\n".join(out)


def _format_source_ref(payload: dict[str, Any] | None) -> str | None:
    """Return a `file:start-end` or `file:line` string from an evidence payload.

    Returns None when the payload is absent, lacks source_ref, or source_ref
    is shaped differently from what Evidence emits (defensive — don't crash
    the renderer on a non-Evidence payload that happened to get `record_type
    == "evidence"` via a primitive's auxiliary record, e.g. init receipts).
    """
    if not isinstance(payload, dict):
        return None
    source_ref = payload.get("source_ref")
    if not isinstance(source_ref, dict):
        return None
    file_ref = source_ref.get("file")
    if not file_ref:
        return None
    line_start = source_ref.get("line_start")
    line_end = source_ref.get("line_end")
    if line_start is None and line_end is None:
        return str(file_ref)
    if line_start is not None and line_end is not None and line_start != line_end:
        return f"{file_ref}:{line_start}-{line_end}"
    # Single line (line_start == line_end) or only one is populated.
    return f"{file_ref}:{line_start or line_end}"
