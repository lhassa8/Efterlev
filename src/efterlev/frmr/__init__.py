"""FRMR loader — parses `FRMR.documentation.json` into the internal model.

FRMR is the authoritative machine-readable FedRAMP 20x requirements file
(version 0.9.43-beta at v0). This module loads it, optionally validates
against `FedRAMP.schema.json`, and produces a `FrmrDocument` pinned to our
internal `Indicator` / `Theme` types so the rest of Efterlev reasons over
our own shapes rather than the upstream raw JSON.

See `catalogs/frmr/FRMR.md` for the upstream structure guide and
`docs/architecture.md` §"FRMR and 800-53" for how this loader sits in the
overall data flow.
"""

from __future__ import annotations

from efterlev.frmr.loader import FrmrDocument, load_frmr

__all__ = ["FrmrDocument", "load_frmr"]
