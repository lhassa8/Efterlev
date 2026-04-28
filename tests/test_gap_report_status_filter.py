"""Tests for the status-filter pills on the gap report.

Priority 2.5 (2026-04-27). Filter-by-status is the most actionable
reviewer feature: click "Not implemented" → all other classifications
hide. Implementation is vanilla JS; the rendered HTML must carry the
right data-attribute hooks (data-status on every classification card,
summary row, and filter button) for the JS to drive.

Tests cover the rendered HTML's data-attribute presence + DOM shape.
The JS itself is small and tested by visual inspection in a browser
(documented in PR #56's body); we assert the script tag is embedded
and the handlers reference the right selectors.
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


# --- filter bar rendering --------------------------------------------------


def test_filter_bar_renders_above_classifications() -> None:
    """When there are classifications, the filter bar appears between
    Summary and the per-KSI cards."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    assert 'class="filter-bar"' in html
    assert "<h2>Classifications</h2>" in html
    # Filter-bar appears after the Classifications heading and before the
    # first .record.claim card.
    classifications_idx = html.index("<h2>Classifications</h2>")
    filter_bar_idx = html.index('class="filter-bar"')
    record_idx = html.index('class="record claim"')
    assert classifications_idx < filter_bar_idx < record_idx


def test_filter_bar_omitted_when_no_classifications() -> None:
    """An empty report has no classifications to filter — bar omitted."""
    html = render_gap_report_html(_report(), **_kwargs())
    assert 'class="filter-bar"' not in html
    assert "<h2>Classifications</h2>" not in html


def test_filter_bar_has_one_button_per_status_plus_all() -> None:
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    expected_statuses = (
        "all",
        "implemented",
        "partial",
        "not_implemented",
        "evidence_layer_inapplicable",
        "not_applicable",
    )
    for status in expected_statuses:
        assert f'data-status="{status}"' in html


def test_all_button_starts_active() -> None:
    """Default state on render is "All selected" — the All button has
    `class="filter-btn active"`. JS toggles `.active` on click."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    assert 'class="filter-btn active" data-status="all"' in html


# --- data-status hooks on cards and rows ----------------------------------


def test_classification_cards_carry_data_status() -> None:
    """Each `.record.claim` card carries `data-status="<status>"` so the
    JS can hide/show by status."""
    html = render_gap_report_html(
        _report(
            _classification("KSI-SVC-SNT", status="implemented"),
            _classification("KSI-IAM-MFA", status="not_implemented"),
        ),
        **_kwargs(),
    )
    assert 'data-status="implemented"' in html
    assert 'data-status="not_implemented"' in html


def test_summary_table_rows_carry_data_status() -> None:
    """The Summary table rows also carry data-status so the same filter
    JS hides matching rows in the summary table."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    assert '<tr data-status="partial">' in html


# --- JS embedding ---------------------------------------------------------


def test_filter_script_embedded() -> None:
    """The vanilla-JS handler is embedded inline (no external CDN per
    Priority 2's self-contained constraint)."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    assert "<script>" in html
    # The handler queries `.filter-bar` and toggles `.filter-hidden`.
    assert ".filter-bar" in html
    assert "filter-hidden" in html


def test_filter_hidden_css_class_defined() -> None:
    """The `.filter-hidden` class must be defined as `display: none` so
    JS-applied filtering actually hides elements."""
    html = render_gap_report_html(
        _report(_classification("KSI-SVC-SNT", status="partial")),
        **_kwargs(),
    )
    assert ".filter-hidden" in html
    assert "display: none" in html


# --- progressive enhancement (no JS) ---------------------------------------


def test_filter_bar_does_not_break_no_js_view() -> None:
    """With JS disabled the buttons render but no card is hidden — the
    `filter-hidden` class is only ever applied by the JS, never via the
    initial render. Acceptance criterion: 'must remain readable with
    JavaScript disabled (filter/sort gracefully degrade to all results
    visible, sorted by KSI)'."""
    html = render_gap_report_html(
        _report(
            _classification("KSI-SVC-SNT", status="implemented"),
            _classification("KSI-IAM-MFA", status="not_implemented"),
        ),
        **_kwargs(),
    )
    # No `class="filter-hidden"` on any rendered element. The class is
    # defined in the stylesheet (so it shows up there), but never
    # applied to a record/row at render time.
    assert 'class="record claim filter-hidden"' not in html
    assert 'class="filter-hidden"' not in html
    assert "filter-hidden filter-hidden" not in html
