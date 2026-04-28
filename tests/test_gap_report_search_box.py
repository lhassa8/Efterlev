"""Tests for the search box on the gap report.

Priority 2.6 (2026-04-27). Free-text search filters classification
cards (and Summary-table rows) by substring match against the card's
text content. Cards/rows that don't contain the query are hidden via
`.search-hidden` class. Combines additively with the status filter
(both can be active; both classes hide via display:none).

Tests cover the rendered HTML's hooks. JS behavior is tested by
visual inspection in a browser; we assert the DOM structure JS needs
is in place.
"""

from __future__ import annotations

from datetime import UTC, datetime

from efterlev.agents import GapReport
from efterlev.agents.gap import KsiClassification
from efterlev.reports import render_gap_report_html


def _classification(
    ksi_id: str = "KSI-SVC-SNT",
    status: str = "partial",
) -> KsiClassification:
    return KsiClassification(
        ksi_id=ksi_id,
        status=status,  # type: ignore[arg-type]
        rationale="...",
        evidence_ids=["sha256:" + "a" * 64] if status in ("implemented", "partial") else [],
    )


def _report(*classifications: KsiClassification) -> GapReport:
    return GapReport(
        ksi_classifications=list(classifications),
        unmapped_findings=[],
        claim_record_ids=[],
    )


def _kwargs() -> dict:
    return {
        "baseline_id": "fedramp-20x-moderate",
        "frmr_version": "0.9.43-beta",
        "generated_at": datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC),
    }


# --- search input rendering ------------------------------------------------


def test_search_input_renders_when_classifications_present() -> None:
    """The search box appears inside the filter bar when there are
    classifications to search."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    assert 'type="search"' in html
    assert 'id="card-search"' in html
    assert 'class="search-input"' in html


def test_search_count_element_present() -> None:
    """Live-region span shows match count once user types."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    assert 'id="search-count"' in html
    assert 'aria-live="polite"' in html


def test_search_omitted_when_no_classifications() -> None:
    """Empty report — no filter bar at all, so no search input either."""
    html = render_gap_report_html(_report(), **_kwargs())
    assert 'id="card-search"' not in html
    assert 'class="search-input"' not in html


def test_search_input_has_descriptive_placeholder() -> None:
    """Placeholder names the searchable surfaces so users know what hits."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    # Placeholder mentions the canonical searchable fields.
    assert 'placeholder="Search KSI, control, detector, rationale, evidence id..."' in html


# --- search-hidden CSS class ----------------------------------------------


def test_search_hidden_class_defined_and_combines_with_filter_hidden() -> None:
    """Both `.filter-hidden` and `.search-hidden` apply display:none, so the
    two filter mechanisms compose additively (an element is hidden if
    EITHER condition matches)."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    assert ".search-hidden" in html
    # Both classes use the same display:none rule.
    assert ".filter-hidden, .search-hidden" in html


# --- JS handler ------------------------------------------------------------


def test_search_handler_registered() -> None:
    """The JS attaches an `input` event listener on `#card-search` and runs
    `applySearch` to toggle `.search-hidden` on cards/rows whose
    textContent doesn't contain the query."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    assert "addEventListener('input'" in html
    assert "applySearch" in html
    assert "search-hidden" in html
    # Debounced (80ms is the chosen value).
    assert "setTimeout(applySearch, 80)" in html


def test_search_targets_classification_cards_and_summary_rows() -> None:
    """Search matches against `.record.claim` cards AND `tr[data-status]`
    Summary-table rows."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    assert ".record.claim, tr[data-status]" in html


# --- progressive enhancement ----------------------------------------------


def test_search_hidden_not_applied_at_render_time() -> None:
    """With JS disabled the search input renders but typing does nothing —
    the `.search-hidden` class is only ever applied by JS, never embedded
    in the initial HTML. No-JS view: all results visible."""
    html = render_gap_report_html(
        _report(
            _classification("KSI-SVC-SNT", status="implemented"),
            _classification("KSI-IAM-MFA", status="not_implemented"),
        ),
        **_kwargs(),
    )
    # `.search-hidden` appears only in CSS / JS strings, not as a class
    # on a rendered card or row.
    assert 'class="record claim search-hidden"' not in html
    assert 'class="filter-hidden search-hidden"' not in html
