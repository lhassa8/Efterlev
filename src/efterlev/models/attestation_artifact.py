"""FRMR-compatible attestation artifact — the v1 Phase 2 primary output.

`AttestationArtifact` is the shape Efterlev serializes to disk for
downstream consumption (3PAO review, RegScale OSCAL-Hub ingestion v1.5+,
CSP package assembly). It is structurally inspired by the FRMR
documentation format — theme-keyed KSI indicators, top-level `info` block,
canonical JSON — but carries attestation data rather than catalog data, so
it is not a valid FRMR documentation file and is not validated against
`catalogs/frmr/FedRAMP.schema.json`. That schema describes the FRMR
catalog; FedRAMP has not published an attestation-output schema as of
April 2026. See DECISIONS 2026-04-22 "Phase 2: FRMR attestation generator"
for the schema-posture design call.

Validation: Pydantic enforces structure at construction time with
`extra="forbid"` and strict literal types. A malformed artifact raises
`ValidationError` before the generator returns. An external JSON Schema
mirror is a follow-up (`catalogs/efterlev/efterlev-attestation.schema.json`)
for consumers who want to validate the serialized file without a Python
dependency.

Trust posture: the artifact always carries a `provenance.requires_review`
flag and a `review_banner` string in the serialized output — the draft-not-
authorization commitment from CLAUDE.md Principle 7 is visible in every
emitted file.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from efterlev.models.attestation_draft import (
    AttestationCitation,
    AttestationMode,
    AttestationStatus,
)

ArtifactTool = Literal["efterlev"]


class AttestationArtifactInfo(BaseModel):
    """Top-level metadata block. Mirrors FRMR's `info` shape."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: ArtifactTool = "efterlev"
    tool_version: str
    # SPEC-57.3 (2026-04-25, 3PAO review §7): the artifact format version
    # is distinct from `frmr_version` so downstream consumers can version-
    # gate against the artifact shape independently of the upstream catalog
    # version. CR26 (mid-2026, est.) will likely bump FRMR; this field
    # stays at "1" unless Efterlev makes a breaking change to the artifact
    # shape itself. Bump policy:
    #   - new optional fields → no bump
    #   - new required fields → bump
    #   - renamed/removed fields → bump
    #   - semantic changes to existing field interpretations → bump
    # Pre-SPEC-57 artifacts implicitly have format version "0" — consumers
    # must default to "0" when this field is absent.
    attestation_format_version: str = "1"
    baseline: str
    frmr_version: str
    frmr_last_updated: str
    generated_at: datetime
    scope: str = (
        "KSI-level attestation draft. NOT a FedRAMP authorization, NOT a 3PAO "
        "assessment. Every narrative entry requires human review before "
        "submission. See `provenance.review_banner` below."
    )


class AttestationArtifactIndicator(BaseModel):
    """Per-indicator attestation record inside the artifact.

    Fields parallel `AttestationDraft` plus the controls split (`controls_mapped`
    + `controls_evidenced` per SPEC-57.2) and `claim_record_id` (if the agent
    persisted a provenance record for this draft). Readers diffing the
    artifact against the FRMR catalog can align by indicator id; readers
    walking provenance can follow `claim_record_id` back to the narrative
    Claim.

    Why two control lists (SPEC-57.2, 2026-04-25, 3PAO review §5):
    `controls_mapped` is the FRMR catalog's list for the KSI — what the
    catalog says this KSI covers regardless of what the scanner saw.
    `controls_evidenced` is the union of `Evidence.controls_evidenced`
    across the cited evidence — what the scan actually proved. A 3PAO
    reviewing the artifact reads `controls_evidenced` for "what was
    demonstrated" and `controls_mapped` for "what would be demonstrated
    by full coverage of this KSI." Merging the two (the v0 behavior,
    dropped here) overstated evidenced coverage by listing every
    FRMR-mapped control as if the scan touched it.

    Granularity note: the two lists overlap at the **control family**
    level, not always at the exact-match level. Caught in the live
    SPEC-57 dogfood — KSI-IAM-ELP's `controls_mapped` includes AC-2.5
    and AC-2.6 (specific enhancements per FRMR's mapping choice); the
    detector evidences AC-2 (the parent, which encompasses both
    enhancements). Both are honest claims at different granularities. A
    reviewer comparing the two lists should treat AC-2 in evidenced as
    "covers any AC-2.* in mapped." Documented behavior, not a defect;
    an explicit overlap-checking helper may land in v0.2 if downstream
    consumers ask for one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: AttestationMode
    status: AttestationStatus | None = None
    narrative: str | None = None
    citations: list[AttestationCitation] = Field(default_factory=list)
    controls_mapped: list[str] = Field(default_factory=list)
    controls_evidenced: list[str] = Field(default_factory=list)
    claim_record_id: str | None = None
    # CSX-SUM cadence fields. Each indicator carries the workspace's
    # declared cadence verbatim; per-KSI override is not yet supported
    # (FRMR has no per-KSI cadence vocabulary today). Optional for backward
    # compatibility — pre-2026-04-29 artifacts have these absent and
    # consumers must default to "<unspecified>" or pull from the customer's
    # CI configuration directly. New optional fields don't bump
    # `attestation_format_version` per the policy in AttestationArtifactInfo.
    machine_validation_cadence: str | None = None
    non_machine_validation_cadence: str | None = None


class AttestationArtifactTheme(BaseModel):
    """FRMR-shaped theme container: `{indicators: {KSI-ID: indicator-record}}`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    indicators: dict[str, AttestationArtifactIndicator] = Field(default_factory=dict)


class AttestationArtifactProvenance(BaseModel):
    """Draft-posture commitment carried in every emitted artifact.

    `requires_review=True` is a hard invariant at v1: Efterlev never
    produces a "final, no-review-needed" attestation. When the Phase 5
    review-workflow landing sets `reviewed_by` and `approved_by`, THIS
    flag stays true — the review-trail fields are additive; the requires-
    review guarantee is what the tool promises, not what a reviewer
    promises about their own work.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requires_review: Literal[True] = True
    review_banner: str = (
        "DRAFT — requires human review. Generated by Efterlev from detector "
        "evidence and human-authored Evidence Manifests. Not a FedRAMP "
        "authorization; not a 3PAO assessment. A qualified reviewer must "
        "validate every narrative and citation before this artifact is "
        "submitted to any authorizing body."
    )


class AttestationArtifact(BaseModel):
    """Complete FRMR-compatible attestation artifact.

    Top-level keys chosen to parallel FRMR documentation: `info` block,
    `KSI` keyed by theme short_name. The `provenance` block is our
    addition (FRMR's catalog has no equivalent — the CSP-attestation
    story is what Efterlev produces and FRMR does not).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    info: AttestationArtifactInfo
    KSI: dict[str, AttestationArtifactTheme] = Field(default_factory=dict)
    provenance: AttestationArtifactProvenance = Field(
        default_factory=lambda: AttestationArtifactProvenance()
    )

    @property
    def indicator_count(self) -> int:
        """Total number of indicators across all themes in this artifact."""
        return sum(len(theme.indicators) for theme in self.KSI.values())
