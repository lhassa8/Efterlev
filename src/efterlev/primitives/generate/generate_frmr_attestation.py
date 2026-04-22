"""`generate_frmr_attestation` primitive — serialize drafts to FRMR-compatible JSON.

Takes a list of `AttestationDraft` objects produced by the Documentation
Agent (mode="agent_drafted") or `generate_frmr_skeleton` (mode="scanner_only")
plus baseline/FRMR metadata, and emits one `AttestationArtifact` — the v1
Phase 2 primary production output. The primitive is deterministic: no LLM
call inside, same input → byte-identical output.

Reopens DECISIONS 2026-04-21 "Documentation Agent composition scope":
that entry deferred a standalone `generate_frmr_attestation` primitive
on the argument that the composition was ~10 lines of assembly with
exactly one caller (the agent). Phase 2 makes the case to promote it:

  - The serialized artifact (a single JSON file covering many KSIs) is
    the v1 primary output and must be independently reachable by MCP
    consumers, CI pipelines, and users who skip the agent and accept
    scanner-only drafts.
  - A future batch-rebuild workflow (rescore a stored set of Claims
    against a new FRMR version, rebuild the artifact, no new LLM calls)
    lands here cleanly as a pure deterministic function.
  - The per-KSI agent composition stays in `DocumentationAgent.run`;
    this primitive operates at a different level — whole-baseline
    artifact assembly, not per-KSI narrative composition.

Schema posture: the artifact's structure is FRMR-inspired (theme→indicator
nesting, `info`+`KSI` top-level keys) but is not a valid FRMR *catalog*
document. `catalogs/frmr/FedRAMP.schema.json` is FedRAMP's schema for the
FRMR documentation catalog; FedRAMP has not published an attestation-output
schema as of April 2026. Pydantic's `extra="forbid"` + strict literals are
what guarantee structure today; a published JSON Schema mirror is a
follow-up. See DECISIONS 2026-04-22 "Phase 2: FRMR attestation generator"
for the full design call.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from efterlev import __version__ as efterlev_version
from efterlev.errors import ValidationError as EfterlevValidationError
from efterlev.models import (
    AttestationArtifact,
    AttestationArtifactIndicator,
    AttestationArtifactInfo,
    AttestationArtifactTheme,
    AttestationDraft,
    Indicator,
)
from efterlev.primitives.base import primitive

_FRMR_ATTESTATION_VERSION = "0.1.0"


class GenerateFrmrAttestationInput(BaseModel):
    """Input: drafts to bundle, the FRMR indicator catalog, baseline provenance tags."""

    model_config = ConfigDict(frozen=True)

    drafts: list[AttestationDraft] = Field(default_factory=list)
    indicators: dict[str, Indicator]
    baseline_id: str
    frmr_version: str
    frmr_last_updated: str
    # Optional per-KSI provenance record IDs; keyed by ksi_id. Carried through
    # to the artifact so a later provenance walker can jump from an indicator
    # entry to the underlying Claim without re-reading the store.
    claim_record_ids: dict[str, str] = Field(default_factory=dict)
    # Override for tests that need deterministic `generated_at`. Production
    # callers leave this as None and the primitive stamps UTC now.
    generated_at: datetime | None = None


class GenerateFrmrAttestationOutput(BaseModel):
    """Output: typed artifact + canonical JSON string + indicator count for logs."""

    model_config = ConfigDict(frozen=True)

    artifact: AttestationArtifact
    artifact_json: str
    indicator_count: int
    skipped_unknown_ksi: list[str] = Field(default_factory=list)


@primitive(capability="generate", side_effects=False, version="0.1.0", deterministic=True)
def generate_frmr_attestation(
    input: GenerateFrmrAttestationInput,
) -> GenerateFrmrAttestationOutput:
    """Assemble an FRMR-compatible AttestationArtifact from a set of drafts.

    Per-draft handling:
      - A draft whose `ksi_id` is not present in `input.indicators` is
        reported in `skipped_unknown_ksi` and omitted from the artifact.
        We do NOT invent a theme attribution; a KSI absent from the loaded
        baseline does not belong in a baseline-targeted artifact.
      - A draft whose KSI is valid is placed under its theme's short_name
        (e.g. KSI-AFR-FSI → `KSI["AFR"].indicators["KSI-AFR-FSI"]`).
      - If multiple drafts target the same KSI id the last one wins; the
        caller is responsible for deduplication upstream (the Documentation
        Agent does this naturally by classifying each KSI once).

    Validation: Pydantic `extra="forbid"` at construction time is the
    structural guarantee. Any drift between the internal model and the
    emitted JSON surfaces as a ValidationError before return.
    """
    now = input.generated_at if input.generated_at is not None else datetime.now(UTC)

    themes: dict[str, dict[str, AttestationArtifactIndicator]] = {}
    skipped: list[str] = []

    for draft in input.drafts:
        indicator = input.indicators.get(draft.ksi_id)
        if indicator is None:
            skipped.append(draft.ksi_id)
            continue

        theme_key = indicator.theme
        artifact_indicator = AttestationArtifactIndicator(
            mode=draft.mode,
            status=draft.status,
            narrative=draft.narrative,
            citations=list(draft.citations),
            controls=list(indicator.controls),
            claim_record_id=input.claim_record_ids.get(draft.ksi_id),
        )
        themes.setdefault(theme_key, {})[draft.ksi_id] = artifact_indicator

    ksi_block: dict[str, AttestationArtifactTheme] = {
        theme_key: AttestationArtifactTheme(indicators=indicators)
        for theme_key, indicators in sorted(themes.items())
    }

    try:
        artifact = AttestationArtifact(
            info=AttestationArtifactInfo(
                tool_version=efterlev_version,
                baseline=input.baseline_id,
                frmr_version=input.frmr_version,
                frmr_last_updated=input.frmr_last_updated,
                generated_at=now,
            ),
            KSI=ksi_block,
        )
    except PydanticValidationError as e:  # pragma: no cover — construction shouldn't fail
        raise EfterlevValidationError(
            f"generate_frmr_attestation failed to construct a valid artifact: {e}"
        ) from e

    # Canonical JSON: sorted keys, no trailing whitespace, UTF-8, newline-terminated.
    # The byte sequence is stable across runs for a given input — required for
    # reproducibility, content-hashable audit trails, and Phase 4 drift workflows.
    # Determinism note: `generated_at` is part of the input model, so "same input"
    # includes a pinned timestamp. Callers that don't pin `generated_at` get
    # `datetime.now(UTC)` stamped inside, which varies per call — that's the
    # intended semantic ("the moment this artifact was produced"), not a loss
    # of determinism.
    payload: dict[str, Any] = artifact.model_dump(mode="json")
    artifact_json = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"

    # Dedupe skipped KSIs while preserving first-seen order. Consumers need a
    # unique list for display; the primitive contract should provide it
    # directly rather than push the dedupe responsibility to every caller.
    seen: set[str] = set()
    skipped_unique: list[str] = []
    for ksi in skipped:
        if ksi not in seen:
            seen.add(ksi)
            skipped_unique.append(ksi)

    return GenerateFrmrAttestationOutput(
        artifact=artifact,
        artifact_json=artifact_json,
        indicator_count=artifact.indicator_count,
        skipped_unknown_ksi=skipped_unique,
    )
