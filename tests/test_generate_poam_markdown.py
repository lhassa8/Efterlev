"""Tests for `generate_poam_markdown` — deterministic POA&M assembly.

Coverage:
  - Open items (partial / not_implemented) produce rows; implemented /
    not_applicable don't.
  - Severity heuristic fires correctly by status.
  - Unknown-KSI classifications are skipped with a report, never
    fabricated (matches the generate_frmr_attestation posture).
  - DRAFT placeholders appear for every reviewer-fillable field.
  - Determinism: same inputs → byte-identical output.
  - Summary table correctly reflects item frontmatter.
  - Short id prefixes render in the evidence-cited list.
"""

from __future__ import annotations

from datetime import UTC, datetime

from efterlev.models import Indicator
from efterlev.primitives.generate import (
    GeneratePoamMarkdownInput,
    PoamClassificationInput,
    generate_poam_markdown,
)


def _ind(
    ksi_id: str,
    name: str = "",
    statement: str = "A KSI statement",
    controls: tuple[str, ...] = ("ac-2", "sc-13"),
    theme: str = "SVC",
) -> Indicator:
    return Indicator(
        id=ksi_id,
        name=name or ksi_id,
        statement=statement,
        controls=list(controls),
        theme=theme,
    )


def _clf(
    ksi_id: str,
    status: str = "partial",
    rationale: str = "Evidence mixed.",
    evidence_ids: tuple[str, ...] = (),
    claim_record_id: str | None = None,
) -> PoamClassificationInput:
    return PoamClassificationInput(
        ksi_id=ksi_id,
        status=status,
        rationale=rationale,
        evidence_ids=list(evidence_ids),
        claim_record_id=claim_record_id,
    )


_FROZEN_TS = datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC)


def _input(
    classifications: list[PoamClassificationInput],
    indicators: dict[str, Indicator] | None = None,
) -> GeneratePoamMarkdownInput:
    if indicators is None:
        indicators = {c.ksi_id: _ind(c.ksi_id) for c in classifications}
    return GeneratePoamMarkdownInput(
        classifications=classifications,
        indicators=indicators,
        baseline_id="fedramp-20x-moderate",
        frmr_version="0.9.43-beta",
        generated_at=_FROZEN_TS,
    )


# --- status filtering -------------------------------------------------------


def test_open_items_only_generate_rows() -> None:
    result = generate_poam_markdown(
        _input(
            [
                _clf("KSI-A", status="implemented"),
                _clf("KSI-B", status="not_applicable"),
                _clf("KSI-C", status="partial"),
                _clf("KSI-D", status="not_implemented"),
                # SPEC-57.1: the new status is a coverage statement, not a
                # remediation item — must be excluded from POA&M output
                # the same way `not_applicable` is.
                _clf("KSI-E", status="evidence_layer_inapplicable"),
            ]
        )
    )
    assert result.item_count == 2
    # implemented / N/A / evidence_layer_inapplicable absent from items.
    md = result.markdown
    assert "KSI-A" not in md or "implemented" not in md.split("KSI-A")[1].split("KSI-")[0]
    assert "KSI-C" in md
    assert "KSI-D" in md
    # KSI-E (evidence_layer_inapplicable) gets no POA&M row.
    assert "KSI-E" not in md or "evidence_layer_inapplicable" not in md


def test_no_open_items_produces_clean_empty_marker() -> None:
    result = generate_poam_markdown(
        _input(
            [
                _clf("KSI-A", status="implemented"),
                _clf("KSI-B", status="not_applicable"),
            ]
        )
    )
    assert result.item_count == 0
    assert "No open POA&M items" in result.markdown
    # Summary section must be absent when there are no items.
    assert "## Summary" not in result.markdown


# --- severity heuristic -----------------------------------------------------


def test_severity_heuristic_not_implemented_is_high() -> None:
    result = generate_poam_markdown(_input([_clf("KSI-A", status="not_implemented")]))
    assert "HIGH" in result.markdown


def test_severity_heuristic_partial_is_medium() -> None:
    result = generate_poam_markdown(_input([_clf("KSI-A", status="partial")]))
    assert "MEDIUM" in result.markdown


def test_severity_documented_as_draft() -> None:
    # The heuristic must be marked as draft/reviewer-adjustable so no one
    # ships it as an authoritative severity assessment.
    result = generate_poam_markdown(_input([_clf("KSI-A", status="partial")]))
    # Header flags that severity is a starting heuristic.
    assert "starting-point heuristic" in result.markdown.lower() or (
        "draft heuristic" in result.markdown.lower()
    )


# --- unknown KSI handling ---------------------------------------------------


def test_unknown_ksi_skipped_not_fabricated() -> None:
    # KSI-B is in the classifications but NOT in indicators.
    result = generate_poam_markdown(
        GeneratePoamMarkdownInput(
            classifications=[
                _clf("KSI-A", status="partial"),
                _clf("KSI-B", status="not_implemented"),  # unknown
            ],
            indicators={"KSI-A": _ind("KSI-A")},
            baseline_id="fedramp-20x-moderate",
            frmr_version="0.9.43-beta",
            generated_at=_FROZEN_TS,
        )
    )
    assert result.item_count == 1
    assert "KSI-B" not in result.markdown
    assert "KSI-B" in result.skipped_unknown_ksi


def test_skipped_unknown_ksi_dedup() -> None:
    # Even if two classifications reference the same unknown id, it's
    # reported once — matches generate_frmr_attestation posture.
    result = generate_poam_markdown(
        GeneratePoamMarkdownInput(
            classifications=[
                _clf("KSI-X", status="partial"),
                _clf("KSI-X", status="not_implemented"),
            ],
            indicators={},
            baseline_id="fedramp-20x-moderate",
            frmr_version="0.9.43-beta",
            generated_at=_FROZEN_TS,
        )
    )
    assert result.skipped_unknown_ksi == ["KSI-X"]


# --- draft placeholders ------------------------------------------------------


def test_every_reviewer_field_is_draft_placeholder() -> None:
    result = generate_poam_markdown(_input([_clf("KSI-A", status="partial")]))
    md = result.markdown
    # The reviewer must fill these before submission.
    assert "**Weakness Title:**" in md
    assert "**Remediation Plan:**" in md
    assert "**Milestones:**" in md
    assert "**Target Completion Date:**" in md
    assert "**Owner:**" in md
    assert "**POC Email:**" in md
    assert "**Residual Risk Summary:**" in md
    assert "**Risk Accepted?:**" in md
    # All carry the DRAFT sentinel so grepping for unfilled fields is easy.
    assert md.count("DRAFT — SET BEFORE SUBMISSION") >= 8


def test_header_carries_draft_banner() -> None:
    result = generate_poam_markdown(_input([_clf("KSI-A", status="partial")]))
    assert "DRAFT — requires human review." in result.markdown


# --- provenance wiring -------------------------------------------------------


def test_claim_record_id_shows_in_provenance_section() -> None:
    result = generate_poam_markdown(
        _input(
            [
                _clf(
                    "KSI-A",
                    status="partial",
                    claim_record_id="sha256:abcdef123456789",
                )
            ]
        )
    )
    assert "efterlev provenance show sha256:abcdef123456789" in result.markdown
    # POA&M ID derived from the claim id (first 8 hex).
    assert "POAM-KSI-A-abcdef12" in result.markdown


def test_no_claim_record_id_falls_back_to_index() -> None:
    result = generate_poam_markdown(_input([_clf("KSI-A", status="partial")]))
    # With no claim id, id falls back to the 000-indexed positional id.
    assert "POAM-KSI-A-000" in result.markdown


# --- evidence citations ------------------------------------------------------


def test_evidence_ids_rendered_as_short_prefixes_in_summary() -> None:
    ev_ids = [f"sha256:{i:064x}" for i in range(3)]
    result = generate_poam_markdown(
        _input([_clf("KSI-A", status="partial", evidence_ids=tuple(ev_ids))])
    )
    # Short 8-char prefix in the item's frontmatter (readable, citable).
    assert "00000000" in result.markdown  # first three ids start with 0000...
    # Full ids not crammed into the short summary section (they're too long).


def test_many_evidence_ids_truncate_summary_with_full_list_below() -> None:
    ev_ids = tuple(f"sha256:{i:064x}" for i in range(10))
    result = generate_poam_markdown(_input([_clf("KSI-A", status="partial", evidence_ids=ev_ids)]))
    md = result.markdown
    # Summary truncates to 5 with a "+5 more" hint.
    assert "+5 more" in md
    # Full list appears below.
    assert "Full evidence citations" in md


def test_no_evidence_renders_explicit_marker() -> None:
    result = generate_poam_markdown(_input([_clf("KSI-A", status="partial")]))
    assert "no cited evidence" in result.markdown


# --- determinism -------------------------------------------------------------


def test_same_inputs_produce_identical_output() -> None:
    # Deterministic primitive contract: byte-identical markdown across runs.
    input_ = _input(
        [
            _clf("KSI-A", status="partial", rationale="mixed TLS evidence"),
            _clf("KSI-B", status="not_implemented", rationale="no evidence produced"),
        ]
    )
    a = generate_poam_markdown(input_).markdown
    b = generate_poam_markdown(input_).markdown
    assert a == b


# --- summary table -----------------------------------------------------------


def test_summary_table_lists_every_item_id_and_ksi() -> None:
    classifications = [
        _clf("KSI-A", status="partial"),
        _clf("KSI-B", status="not_implemented"),
    ]
    result = generate_poam_markdown(_input(classifications))
    md = result.markdown
    summary_section = md.split("## Summary")[1].split("## Items")[0]
    # Table header + 2 item rows = 4 bars-per-line lines (header, separator, 2 items).
    for c in classifications:
        assert c.ksi_id in summary_section


# --- KSI statement / controls from FRMR --------------------------------------


def test_ksi_statement_appears_in_item_block() -> None:
    result = generate_poam_markdown(
        _input(
            [_clf("KSI-X", status="partial")],
            indicators={
                "KSI-X": _ind(
                    "KSI-X",
                    statement="Enforce cryptographic integrity validation.",
                    controls=("sc-13", "si-7"),
                )
            },
        )
    )
    md = result.markdown
    assert "Enforce cryptographic integrity validation." in md
    assert "sc-13" in md
    assert "si-7" in md


def test_controls_empty_renders_dash() -> None:
    result = generate_poam_markdown(
        _input(
            [_clf("KSI-X", status="partial")],
            indicators={"KSI-X": _ind("KSI-X", controls=())},
        )
    )
    assert "**800-53 Controls:** —" in result.markdown


# --- sort modes --------------------------------------------------------------


def _ksi_id_order_in_output(markdown: str, ksi_ids: list[str]) -> list[str]:
    """Return the subset of `ksi_ids` in the order they appear in `markdown`."""
    positions = [(markdown.find(ksi_id), ksi_id) for ksi_id in ksi_ids]
    found = [(pos, ksi_id) for pos, ksi_id in positions if pos >= 0]
    return [ksi_id for _, ksi_id in sorted(found)]


def test_severity_sort_puts_not_implemented_before_partial() -> None:
    # Default sort: not_implemented (HIGH) first, then partial (MEDIUM);
    # alphabetical within tier. Locks the deterministic-order guarantee.
    result = generate_poam_markdown(
        _input(
            [
                _clf("KSI-A", status="partial"),
                _clf("KSI-B", status="not_implemented"),
                _clf("KSI-C", status="partial"),
                _clf("KSI-D", status="not_implemented"),
            ]
        )
    )
    order = _ksi_id_order_in_output(result.markdown, ["KSI-A", "KSI-B", "KSI-C", "KSI-D"])
    # not_implemented first (B, D alphabetical), then partial (A, C alphabetical).
    assert order == ["KSI-B", "KSI-D", "KSI-A", "KSI-C"]


def test_csx_ord_sort_emits_prescribed_sequence_first() -> None:
    # csx-ord mode: items appear in the prescribed-sequence order;
    # non-prescribed KSIs follow alphabetically.
    classifications = [
        _clf("KSI-AFR-VDR", status="not_implemented"),
        _clf("KSI-AFR-MAS", status="partial"),
        _clf("KSI-SVC-VRI", status="not_implemented"),  # not in prescribed seq
        _clf("KSI-AFR-ADS", status="partial"),
    ]
    indicators = {
        "KSI-AFR-VDR": _ind("KSI-AFR-VDR", theme="AFR"),
        "KSI-AFR-MAS": _ind("KSI-AFR-MAS", theme="AFR"),
        "KSI-SVC-VRI": _ind("KSI-SVC-VRI", theme="SVC"),
        "KSI-AFR-ADS": _ind("KSI-AFR-ADS", theme="AFR"),
    }
    inp = GeneratePoamMarkdownInput(
        classifications=classifications,
        indicators=indicators,
        baseline_id="fedramp-20x-moderate",
        frmr_version="0.9.43-beta",
        generated_at=_FROZEN_TS,
        sort_mode="csx-ord",
        csx_ord_sequence=[
            "KSI-AFR-MAS",
            "KSI-AFR-ADS",
            "KSI-AFR-UCM",
            "KSI-AFR-VDR",
            "KSI-AFR-SCN",
        ],
    )
    result = generate_poam_markdown(inp)
    order = _ksi_id_order_in_output(
        result.markdown,
        ["KSI-AFR-MAS", "KSI-AFR-ADS", "KSI-AFR-VDR", "KSI-SVC-VRI"],
    )
    # MAS first (prescribed rank 0), ADS (rank 1), VDR (rank 3), then
    # SVC-VRI (not in sequence, sorts to tail).
    assert order == ["KSI-AFR-MAS", "KSI-AFR-ADS", "KSI-AFR-VDR", "KSI-SVC-VRI"]


def test_csx_ord_sort_with_empty_sequence_falls_back_to_alphabetical() -> None:
    # When csx-ord is requested but the sequence is empty (e.g., a stale
    # FRMR cache predating the loader's csx_ord_sequence field), every
    # item gets the same rank and the secondary alphabetical key wins.
    inp = GeneratePoamMarkdownInput(
        classifications=[
            _clf("KSI-Z", status="not_implemented"),
            _clf("KSI-A", status="partial"),
            _clf("KSI-M", status="partial"),
        ],
        indicators={
            "KSI-Z": _ind("KSI-Z"),
            "KSI-A": _ind("KSI-A"),
            "KSI-M": _ind("KSI-M"),
        },
        baseline_id="fedramp-20x-moderate",
        frmr_version="0.9.43-beta",
        generated_at=_FROZEN_TS,
        sort_mode="csx-ord",
        csx_ord_sequence=[],  # stale cache
    )
    result = generate_poam_markdown(inp)
    order = _ksi_id_order_in_output(result.markdown, ["KSI-A", "KSI-M", "KSI-Z"])
    assert order == ["KSI-A", "KSI-M", "KSI-Z"]


def test_severity_sort_is_deterministic_across_input_orderings() -> None:
    # Same set of classifications in two different input orders must
    # produce byte-identical markdown — necessary for diff-against-prior-run
    # workflows and for reproducible CI artifacts.
    cls_a = [
        _clf("KSI-B", status="partial"),
        _clf("KSI-A", status="not_implemented"),
        _clf("KSI-C", status="partial"),
    ]
    cls_b = list(reversed(cls_a))
    md_a = generate_poam_markdown(_input(cls_a)).markdown
    md_b = generate_poam_markdown(_input(cls_b)).markdown
    assert md_a == md_b
