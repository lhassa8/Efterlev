"""Tests for the @media print stylesheet (Priority 2.7).

The print stylesheet hides interactive bits (filter bar) and applies
page-break rules so classification cards don't split across pages on
paper. Lives in the shared `RECORDS_STYLESHEET`, so it applies to all
three report types (gap, documentation, remediation).
"""

from __future__ import annotations

from datetime import UTC, datetime

from efterlev.agents import DocumentationReport, GapReport, RemediationProposal
from efterlev.agents.gap import KsiClassification
from efterlev.reports import (
    RECORDS_STYLESHEET,
    render_documentation_report_html,
    render_gap_report_html,
    render_remediation_proposal_html,
)


def _kwargs() -> dict:
    return {
        "baseline_id": "fedramp-20x-moderate",
        "frmr_version": "0.9.43-beta",
        "generated_at": datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC),
    }


# --- shared stylesheet has @media print -----------------------------------


def test_records_stylesheet_includes_media_print_block() -> None:
    """The print rules live in the shared base stylesheet so all three
    report types get them automatically."""
    assert "@media print" in RECORDS_STYLESHEET


def test_print_block_hides_filter_bar() -> None:
    """Interactive filter bar has no purpose on paper — hidden under print."""
    assert ".filter-bar" in RECORDS_STYLESHEET
    # The selector + display: none rule appear in the @media print block.
    media_idx = RECORDS_STYLESHEET.index("@media print")
    print_block = RECORDS_STYLESHEET[media_idx:]
    assert ".filter-bar { display: none" in print_block


def test_print_block_avoids_page_break_inside_records() -> None:
    """Classification cards (.record) shouldn't split across pages."""
    media_idx = RECORDS_STYLESHEET.index("@media print")
    print_block = RECORDS_STYLESHEET[media_idx:]
    assert "page-break-inside: avoid" in print_block
    # Both legacy and modern syntax for cross-browser support.
    assert "break-inside: avoid" in print_block


def test_print_block_expands_out_of_boundary_details() -> None:
    """On paper, expand the collapsed `details` blocks so reviewers see
    everything that was hidden in interactive viewing."""
    media_idx = RECORDS_STYLESHEET.index("@media print")
    print_block = RECORDS_STYLESHEET[media_idx:]
    assert "details.out-of-boundary-collapsed > *:not(summary)" in print_block
    assert "display: block !important" in print_block


def test_print_block_avoids_page_break_after_headings() -> None:
    """Don't orphan a heading at the bottom of a page."""
    media_idx = RECORDS_STYLESHEET.index("@media print")
    print_block = RECORDS_STYLESHEET[media_idx:]
    assert "page-break-after: avoid" in print_block


# --- print rules apply to all 3 report types ------------------------------


def _gap_html() -> str:
    report = GapReport(
        ksi_classifications=[
            KsiClassification(
                ksi_id="KSI-SVC-SNT",
                status="partial",
                rationale="...",
                evidence_ids=["sha256:" + "a" * 64],
            )
        ],
        unmapped_findings=[],
        claim_record_ids=[],
    )
    return render_gap_report_html(report, **_kwargs())


def _doc_html() -> str:
    report = DocumentationReport(attestations=[], skipped_ksi_ids=[])
    return render_documentation_report_html(report, **_kwargs())


def _rem_html() -> str:
    proposal = RemediationProposal(
        ksi_id="KSI-SVC-SNT",
        status="proposed",
        diff="...",
        explanation="...",
        cited_evidence_ids=[],
        cited_source_files=[],
    )
    return render_remediation_proposal_html(
        proposal, generated_at=datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC)
    )


def test_gap_report_includes_print_stylesheet() -> None:
    assert "@media print" in _gap_html()


def test_documentation_report_includes_print_stylesheet() -> None:
    assert "@media print" in _doc_html()


def test_remediation_report_includes_print_stylesheet() -> None:
    assert "@media print" in _rem_html()
