"""Internal attestation draft model.

`AttestationDraft` is the internal shape the Documentation Agent produces
before FRMR serialization. Per DECISIONS 2026-04-21 design call #2 the
draft carries a `mode` flag distinguishing the two trust classes:

  - `scanner_only`: built entirely by the deterministic
    `generate_frmr_skeleton` primitive. Narrative is None, status is None.
    All citations reference real Evidence records in the provenance store.
    This artifact is Evidence-class: a user can cite it without any LLM
    involvement.

  - `agent_drafted`: composed by the Documentation Agent on top of a
    scanner-only skeleton. Narrative is the LLM-drafted prose and must
    carry the "DRAFT — requires human review" banner in rendered output.
    `status` comes from the Gap Agent classification.

FRMR-schema output validation is a v1 concern — FedRAMP hasn't published
an attestation-specific schema yet. When they do, the Pydantic-layer
checks here will grow a `validate_frmr(artifact)` companion primitive.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AttestationMode = Literal["scanner_only", "agent_drafted"]
AttestationStatus = Literal["implemented", "partial", "not_implemented", "not_applicable"]


class AttestationCitation(BaseModel):
    """One evidence citation inside an attestation draft.

    Carries enough metadata for the rendered output to link back to both the
    underlying source file/line and the provenance store (via `evidence_id`).
    `source_lines` is a human-readable range like "12-24" for display; None
    when the evidence is structural (whole-file absence of a resource).
    """

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    detector_id: str
    source_file: str
    source_lines: str | None = None


class AttestationDraft(BaseModel):
    """Internal attestation draft; serialized into FRMR JSON at the output boundary."""

    model_config = ConfigDict(frozen=True)

    ksi_id: str
    baseline_id: str
    frmr_version: str
    mode: AttestationMode
    citations: list[AttestationCitation] = Field(default_factory=list)
    # scanner_only: both None. agent_drafted: both populated.
    status: AttestationStatus | None = None
    narrative: str | None = None
