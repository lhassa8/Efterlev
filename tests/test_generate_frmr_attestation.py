"""`generate_frmr_attestation` primitive tests.

Exercises the Phase 2 FRMR-compatible artifact serializer. Structural
assertions on the emitted artifact (typed AttestationArtifact) and on the
canonical JSON string. Tests mirror the shape of
`test_generate_frmr_skeleton.py`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from efterlev.models import (
    AttestationArtifact,
    AttestationCitation,
    AttestationDraft,
    Indicator,
)
from efterlev.primitives.generate import (
    GenerateFrmrAttestationInput,
    generate_frmr_attestation,
)

_FIXED_NOW = datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)


def _indicator(ksi_id: str, theme: str, controls: list[str]) -> Indicator:
    return Indicator(
        id=ksi_id,
        theme=theme,
        name=f"Indicator {ksi_id}",
        statement="Test indicator statement.",
        controls=controls,
    )


def _draft(
    ksi_id: str,
    *,
    mode: str = "agent_drafted",
    status: str | None = "implemented",
    narrative: str | None = "A narrative.",
    citations: list[AttestationCitation] | None = None,
) -> AttestationDraft:
    return AttestationDraft(
        ksi_id=ksi_id,
        baseline_id="fedramp-20x-moderate",
        frmr_version="0.9.43-beta",
        mode=mode,  # type: ignore[arg-type]
        citations=citations or [],
        status=status,  # type: ignore[arg-type]
        narrative=narrative,
    )


def _input(
    drafts: list[AttestationDraft] | None = None,
    indicators: dict[str, Indicator] | None = None,
    claim_record_ids: dict[str, str] | None = None,
) -> GenerateFrmrAttestationInput:
    return GenerateFrmrAttestationInput(
        drafts=drafts or [],
        indicators=indicators or {},
        baseline_id="fedramp-20x-moderate",
        frmr_version="0.9.43-beta",
        frmr_last_updated="2026-04-01",
        claim_record_ids=claim_record_ids or {},
        generated_at=_FIXED_NOW,
    )


def test_empty_input_produces_valid_empty_artifact() -> None:
    result = generate_frmr_attestation(_input())
    assert isinstance(result.artifact, AttestationArtifact)
    assert result.artifact.KSI == {}
    assert result.indicator_count == 0
    assert result.skipped_unknown_ksi == []
    # The draft-review banner is always in the serialized output,
    # independent of whether any indicators were attested.
    assert result.artifact.provenance.requires_review is True
    assert "DRAFT" in result.artifact.provenance.review_banner


def test_single_draft_lands_under_its_theme() -> None:
    indicator = _indicator("KSI-AFR-FSI", theme="AFR", controls=["ir-6", "ir-7"])
    draft = _draft("KSI-AFR-FSI")
    result = generate_frmr_attestation(
        _input(drafts=[draft], indicators={indicator.id: indicator}),
    )
    assert "AFR" in result.artifact.KSI
    indicators = result.artifact.KSI["AFR"].indicators
    assert "KSI-AFR-FSI" in indicators
    assert indicators["KSI-AFR-FSI"].status == "implemented"
    assert indicators["KSI-AFR-FSI"].narrative == "A narrative."
    assert indicators["KSI-AFR-FSI"].controls == ["ir-6", "ir-7"]


def test_multiple_drafts_group_by_theme() -> None:
    indicators = {
        "KSI-AFR-FSI": _indicator("KSI-AFR-FSI", "AFR", ["ir-6"]),
        "KSI-SVC-SNT": _indicator("KSI-SVC-SNT", "SVC", ["sc-8"]),
        "KSI-SVC-VRI": _indicator("KSI-SVC-VRI", "SVC", ["sc-13"]),
    }
    drafts = [_draft(k) for k in indicators]
    result = generate_frmr_attestation(_input(drafts=drafts, indicators=indicators))
    # AFR theme has 1 indicator; SVC has 2.
    assert set(result.artifact.KSI.keys()) == {"AFR", "SVC"}
    assert len(result.artifact.KSI["AFR"].indicators) == 1
    assert len(result.artifact.KSI["SVC"].indicators) == 2
    assert result.indicator_count == 3


def test_unknown_ksi_draft_is_skipped_not_fabricated() -> None:
    # A draft whose KSI isn't in the loaded indicator set must not land in
    # the artifact — we can't attribute it to a theme we don't know about.
    indicators = {"KSI-AFR-FSI": _indicator("KSI-AFR-FSI", "AFR", ["ir-6"])}
    drafts = [_draft("KSI-AFR-FSI"), _draft("KSI-XXX-YYY")]
    result = generate_frmr_attestation(_input(drafts=drafts, indicators=indicators))
    assert result.skipped_unknown_ksi == ["KSI-XXX-YYY"]
    # Only the known KSI landed.
    assert result.indicator_count == 1
    assert "KSI-AFR-FSI" in result.artifact.KSI["AFR"].indicators


def test_claim_record_id_is_carried_through_when_provided() -> None:
    indicator = _indicator("KSI-AFR-FSI", "AFR", ["ir-6"])
    draft = _draft("KSI-AFR-FSI")
    result = generate_frmr_attestation(
        _input(
            drafts=[draft],
            indicators={indicator.id: indicator},
            claim_record_ids={"KSI-AFR-FSI": "sha256:record123"},
        ),
    )
    assert (
        result.artifact.KSI["AFR"].indicators["KSI-AFR-FSI"].claim_record_id == "sha256:record123"
    )


def test_citations_are_preserved_verbatim() -> None:
    cite = AttestationCitation(
        evidence_id="sha256:abc",
        detector_id="manifest",
        source_file=".efterlev/manifests/security-inbox.yml",
        source_lines=None,
    )
    indicator = _indicator("KSI-AFR-FSI", "AFR", ["ir-6"])
    draft = _draft("KSI-AFR-FSI", citations=[cite])
    result = generate_frmr_attestation(
        _input(drafts=[draft], indicators={indicator.id: indicator}),
    )
    citations = result.artifact.KSI["AFR"].indicators["KSI-AFR-FSI"].citations
    assert len(citations) == 1
    assert citations[0].evidence_id == "sha256:abc"
    assert citations[0].detector_id == "manifest"


def test_artifact_json_is_canonical_and_deterministic() -> None:
    indicator = _indicator("KSI-AFR-FSI", "AFR", ["ir-6"])
    draft = _draft("KSI-AFR-FSI")
    inp = _input(drafts=[draft], indicators={indicator.id: indicator})
    first = generate_frmr_attestation(inp)
    second = generate_frmr_attestation(inp)
    # Same input → byte-identical JSON across runs. Required for
    # content-addressable audit and Phase 4 diff-against-prior-run workflows.
    assert first.artifact_json == second.artifact_json
    # Canonical JSON is sorted-keys and indented.
    parsed = json.loads(first.artifact_json)
    assert parsed["info"]["tool"] == "efterlev"
    assert parsed["info"]["baseline"] == "fedramp-20x-moderate"
    # Top-level keys sorted alphabetically (sort_keys=True).
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_artifact_info_block_carries_baseline_and_frmr_metadata() -> None:
    result = generate_frmr_attestation(_input())
    info = result.artifact.info
    assert info.tool == "efterlev"
    assert info.baseline == "fedramp-20x-moderate"
    assert info.frmr_version == "0.9.43-beta"
    assert info.frmr_last_updated == "2026-04-01"
    assert info.generated_at == _FIXED_NOW
    # scope text is present and names the draft-not-authorization posture.
    assert "not a fedramp authorization" in info.scope.lower()


def test_provenance_block_is_invariant_requires_review_true() -> None:
    # requires_review=True is a hard invariant per CLAUDE.md Principle 7.
    # Confirm Pydantic literals enforce it: trying to emit with False should
    # raise ValidationError.
    from pydantic import ValidationError

    from efterlev.models import AttestationArtifactProvenance

    with pytest.raises(ValidationError):
        AttestationArtifactProvenance(requires_review=False)  # type: ignore[arg-type]


def test_scanner_only_draft_serializes_without_narrative_or_status() -> None:
    indicator = _indicator("KSI-AFR-FSI", "AFR", ["ir-6"])
    draft = _draft("KSI-AFR-FSI", mode="scanner_only", status=None, narrative=None)
    result = generate_frmr_attestation(
        _input(drafts=[draft], indicators={indicator.id: indicator}),
    )
    record = result.artifact.KSI["AFR"].indicators["KSI-AFR-FSI"]
    assert record.mode == "scanner_only"
    assert record.status is None
    assert record.narrative is None


def test_duplicate_ksi_draft_last_wins() -> None:
    indicator = _indicator("KSI-AFR-FSI", "AFR", ["ir-6"])
    first = _draft("KSI-AFR-FSI", narrative="first narrative")
    second = _draft("KSI-AFR-FSI", narrative="second narrative")
    result = generate_frmr_attestation(
        _input(drafts=[first, second], indicators={indicator.id: indicator}),
    )
    assert result.artifact.KSI["AFR"].indicators["KSI-AFR-FSI"].narrative == "second narrative"
    assert result.indicator_count == 1
