"""AttestationDraft model tests — shape and mode invariants only.

Serialization into FRMR JSON is a separate concern tested alongside the
generator primitive that produces it. Here we just confirm the internal
model refuses invalid modes/statuses and accepts both mode/narrative
configurations the Documentation Agent emits.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from efterlev.models import AttestationCitation, AttestationDraft


def _citation() -> AttestationCitation:
    return AttestationCitation(
        evidence_id="abc123",
        detector_id="aws.encryption_s3_at_rest",
        source_file="main.tf",
        source_lines="1-10",
    )


def test_scanner_only_mode_allows_none_narrative_and_status() -> None:
    draft = AttestationDraft(
        ksi_id="KSI-SVC-VRI",
        baseline_id="fedramp-20x-moderate",
        frmr_version="0.9.43-beta",
        mode="scanner_only",
        citations=[_citation()],
    )
    assert draft.narrative is None
    assert draft.status is None
    assert draft.mode == "scanner_only"


def test_agent_drafted_mode_carries_status_and_narrative() -> None:
    draft = AttestationDraft(
        ksi_id="KSI-SVC-VRI",
        baseline_id="fedramp-20x-moderate",
        frmr_version="0.9.43-beta",
        mode="agent_drafted",
        citations=[_citation()],
        status="partial",
        narrative="Infrastructure-layer encryption is in place on the audit bucket.",
    )
    assert draft.mode == "agent_drafted"
    assert draft.status == "partial"
    assert draft.narrative is not None


def test_invalid_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AttestationDraft(
            ksi_id="KSI-SVC-VRI",
            baseline_id="fedramp-20x-moderate",
            frmr_version="0.9.43-beta",
            mode="totally-made-up",  # type: ignore[arg-type]
            citations=[_citation()],
        )


def test_invalid_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AttestationDraft(
            ksi_id="KSI-SVC-VRI",
            baseline_id="fedramp-20x-moderate",
            frmr_version="0.9.43-beta",
            mode="agent_drafted",
            citations=[_citation()],
            status="sort-of-implemented",  # type: ignore[arg-type]
            narrative="x",
        )


def test_empty_citations_list_is_allowed() -> None:
    # A KSI with no attributed evidence still yields a valid draft — the
    # agent will render this as "no evidence found" rather than failing.
    draft = AttestationDraft(
        ksi_id="KSI-SVC-SNT",
        baseline_id="fedramp-20x-moderate",
        frmr_version="0.9.43-beta",
        mode="scanner_only",
    )
    assert draft.citations == []
