"""Efterlev internal data model.

Re-exports the types Phase 1+ code will import. Pydantic v2, frozen (immutable)
for every append-only record, content-addressed ids computed via the shared
helper in `_hashing.py`. See `CLAUDE.md` §"Evidence vs. claims: the data model"
and §"Provenance model" for the authoritative descriptions.

Types deferred to later phases (listed in `CLAUDE.md`'s repo layout but not yet
implemented): `Finding` (scanner aggregation, Phase 2), `Mapping` (v1 Mapping
Agent). `AttestationDraft` landed in Phase 3 with the Documentation Agent work
per DECISIONS 2026-04-21 design call #2.
"""

from __future__ import annotations

from efterlev.models.attestation_draft import (
    AttestationCitation,
    AttestationDraft,
    AttestationMode,
    AttestationStatus,
)
from efterlev.models.claim import Claim, ClaimType, Confidence
from efterlev.models.control import Control, ControlEnhancement
from efterlev.models.evidence import Evidence
from efterlev.models.indicator import Baseline, Indicator, Theme
from efterlev.models.provenance import ProvenanceRecord, RecordType
from efterlev.models.source import TerraformResource
from efterlev.models.source_ref import SourceRef

__all__ = [
    "AttestationCitation",
    "AttestationDraft",
    "AttestationMode",
    "AttestationStatus",
    "Baseline",
    "Claim",
    "ClaimType",
    "Confidence",
    "Control",
    "ControlEnhancement",
    "Evidence",
    "Indicator",
    "ProvenanceRecord",
    "RecordType",
    "SourceRef",
    "TerraformResource",
    "Theme",
]
