"""Provenance store, receipt log, walker, verifier.

Public interface for Phase 1b. Phase 1c wraps the verifier as a `@primitive`;
Phase 2+ wires the store into the `scan` path and every agent call.
"""

from __future__ import annotations

from efterlev.provenance.context import (
    active_store,
    current_primitive,
    get_active_store,
    get_current_primitive,
)
from efterlev.provenance.receipts import ReceiptLog
from efterlev.provenance.store import ProvenanceStore
from efterlev.provenance.verify import VerifyReceiptsReport, verify_receipts
from efterlev.provenance.walker import ChainNode, render_chain_text, walk_chain

__all__ = [
    "ChainNode",
    "ProvenanceStore",
    "ReceiptLog",
    "VerifyReceiptsReport",
    "active_store",
    "current_primitive",
    "get_active_store",
    "get_current_primitive",
    "render_chain_text",
    "verify_receipts",
    "walk_chain",
]
