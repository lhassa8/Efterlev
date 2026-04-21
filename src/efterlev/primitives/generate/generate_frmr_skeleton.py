"""`generate_frmr_skeleton` primitive — scanner-only AttestationDraft assembly.

Takes a KSI id and the evidence records that have been attributed to it,
and produces an `AttestationDraft(mode="scanner_only", narrative=None,
status=None)` with the full citation list. No LLM involvement.

Per DECISIONS 2026-04-21 design call #2 this is the deterministic half of
the Documentation Agent. The agent composes skeleton + narrative-fill in
a separate generative primitive; a user who distrusts LLM prose can stop
at the skeleton and get a scanner-only FRMR-shaped artifact listing what
the detectors actually found.

One `generate_frmr_skeleton` call per KSI. Callers aggregating across the
whole baseline invoke this in a loop rather than batching inside the
primitive — it keeps the primitive's contract one-KSI-in / one-draft-out
and makes provenance records cleanly per-KSI.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from efterlev.models import AttestationCitation, AttestationDraft, Evidence
from efterlev.primitives.base import primitive


class GenerateFrmrSkeletonInput(BaseModel):
    """Input: one KSI + its attributed evidence + baseline/FRMR provenance tags."""

    model_config = ConfigDict(frozen=True)

    ksi_id: str
    evidence: list[Evidence] = Field(default_factory=list)
    baseline_id: str
    frmr_version: str


class GenerateFrmrSkeletonOutput(BaseModel):
    """Output: a single scanner-only AttestationDraft."""

    model_config = ConfigDict(frozen=True)

    draft: AttestationDraft


@primitive(capability="generate", side_effects=False, version="0.1.0", deterministic=True)
def generate_frmr_skeleton(
    input: GenerateFrmrSkeletonInput,
) -> GenerateFrmrSkeletonOutput:
    """Assemble an AttestationDraft with citations only, no narrative, no status.

    Every evidence record in `input.evidence` becomes a citation. The draft
    carries the baseline and FRMR version tags the caller passed so later
    provenance walks (and v1 OSCAL generators) can identify which catalog
    the skeleton was built against without re-reading the store.
    """
    citations: list[AttestationCitation] = []
    for ev in input.evidence:
        citations.append(
            AttestationCitation(
                evidence_id=ev.evidence_id,
                detector_id=ev.detector_id,
                source_file=str(ev.source_ref.file),
                source_lines=_format_line_range(ev.source_ref.line_start, ev.source_ref.line_end),
            )
        )

    draft = AttestationDraft(
        ksi_id=input.ksi_id,
        baseline_id=input.baseline_id,
        frmr_version=input.frmr_version,
        mode="scanner_only",
        citations=citations,
        status=None,
        narrative=None,
    )
    return GenerateFrmrSkeletonOutput(draft=draft)


def _format_line_range(start: int | None, end: int | None) -> str | None:
    """Render `line_start`/`line_end` as a single human-readable string, or None."""
    if start is None and end is None:
        return None
    if start is not None and end is not None and start != end:
        return f"{start}-{end}"
    return str(start if start is not None else end)
