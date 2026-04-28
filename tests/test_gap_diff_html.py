"""Tests for `render_gap_diff_html` (Priority 2.10b).

The HTML renderer takes a `GapDiff` (from `compute_gap_diff`) and
produces a complete HTML document with categorized sections:
Regressed (top, action items), Added, Improved, Shifted, Removed,
Unchanged (collapsed).
"""

from __future__ import annotations

from datetime import UTC, datetime

from efterlev.reports import GapDiff, KsiDiffEntry, compute_gap_diff, render_gap_diff_html


def _diff_with(*entries: KsiDiffEntry) -> GapDiff:
    return GapDiff(
        prior_generated_at="2026-04-20T12:00:00+00:00",
        current_generated_at="2026-04-28T12:00:00+00:00",
        prior_baseline_id="fedramp-20x-moderate",
        current_baseline_id="fedramp-20x-moderate",
        entries=list(entries),
    )


def _kwargs() -> dict:
    return {"generated_at": datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC)}


# --- document shell --------------------------------------------------------


def test_renders_complete_html_document() -> None:
    html = render_gap_diff_html(_diff_with(), **_kwargs())
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>Gap Diff — Efterlev</title>" in html


def test_summary_pills_render_with_counts() -> None:
    """Top summary line shows pill counts for each category."""
    diff = _diff_with(
        KsiDiffEntry(ksi_id="KSI-A", outcome="added", current_status="implemented"),
        KsiDiffEntry(ksi_id="KSI-B", outcome="removed", prior_status="partial"),
        KsiDiffEntry(
            ksi_id="KSI-C",
            outcome="status_changed",
            prior_status="partial",
            current_status="implemented",
            severity_movement="improved",
        ),
        KsiDiffEntry(
            ksi_id="KSI-D",
            outcome="status_changed",
            prior_status="implemented",
            current_status="not_implemented",
            severity_movement="regressed",
        ),
        KsiDiffEntry(
            ksi_id="KSI-E",
            outcome="unchanged",
            prior_status="implemented",
            current_status="implemented",
        ),
    )
    html = render_gap_diff_html(diff, **_kwargs())
    assert "1 added" in html
    assert "1 removed" in html
    assert "1 improved" in html
    assert "1 regressed" in html
    assert "1 unchanged" in html


def test_metadata_propagated_into_meta_line() -> None:
    html = render_gap_diff_html(_diff_with(), **_kwargs())
    assert "2026-04-20T12:00:00+00:00" in html
    assert "2026-04-28T12:00:00+00:00" in html
    assert "fedramp-20x-moderate" in html


# --- per-section rendering ------------------------------------------------


def test_regressed_section_renders_first() -> None:
    """Regressed are the action items — render at the top."""
    diff = _diff_with(
        KsiDiffEntry(ksi_id="KSI-A", outcome="added", current_status="implemented"),
        KsiDiffEntry(
            ksi_id="KSI-B",
            outcome="status_changed",
            prior_status="implemented",
            current_status="not_implemented",
            severity_movement="regressed",
        ),
    )
    html = render_gap_diff_html(diff, **_kwargs())
    regressed_idx = html.index("Regressed (1)")
    added_idx = html.index("Added (1)")
    assert regressed_idx < added_idx


def test_regressed_table_shows_was_and_now_status() -> None:
    diff = _diff_with(
        KsiDiffEntry(
            ksi_id="KSI-SVC-SNT",
            outcome="status_changed",
            prior_status="implemented",
            current_status="not_implemented",
            severity_movement="regressed",
        )
    )
    html = render_gap_diff_html(diff, **_kwargs())
    assert "Regressed (1)" in html
    assert "KSI-SVC-SNT" in html
    # Both prior and current statuses render with their pills.
    assert "status-implemented" in html
    assert "status-not_implemented" in html


def test_added_section_present_when_added_entries() -> None:
    diff = _diff_with(KsiDiffEntry(ksi_id="KSI-NEW", outcome="added", current_status="implemented"))
    html = render_gap_diff_html(diff, **_kwargs())
    assert "Added (1)" in html
    assert "KSI-NEW" in html


def test_improved_section_present_when_improved_entries() -> None:
    diff = _diff_with(
        KsiDiffEntry(
            ksi_id="KSI-IMP",
            outcome="status_changed",
            prior_status="not_implemented",
            current_status="partial",
            severity_movement="improved",
        )
    )
    html = render_gap_diff_html(diff, **_kwargs())
    assert "Improved (1)" in html


def test_unchanged_section_collapsed_under_details() -> None:
    """Unchanged is verbose; collapse it under <details> so reviewers
    focus on the actionable categories first."""
    diff = _diff_with(
        KsiDiffEntry(
            ksi_id="KSI-UNCH",
            outcome="unchanged",
            prior_status="implemented",
            current_status="implemented",
        )
    )
    html = render_gap_diff_html(diff, **_kwargs())
    assert '<details class="unchanged-collapsed">' in html
    assert "Unchanged (1)" in html


def test_empty_diff_renders_complete_document() -> None:
    """A diff with no entries (no changes between two identical reports)
    still produces a valid document with all-zero summary pills."""
    html = render_gap_diff_html(_diff_with(), **_kwargs())
    assert "0 added" in html
    assert "0 regressed" in html
    # No section tables rendered.
    assert "Regressed (" not in html or "Regressed (0)" not in html


# --- end-to-end: compute + render -----------------------------------------


def test_round_trip_compute_then_render() -> None:
    """Realistic flow: compute diff from two sidecars, render HTML."""
    prior = {
        "schema_version": "1.0",
        "report_type": "gap",
        "generated_at": "2026-04-20T12:00:00+00:00",
        "baseline_id": "fedramp-20x-moderate",
        "ksi_classifications": [
            {"ksi_id": "KSI-SVC-SNT", "status": "implemented"},
            {"ksi_id": "KSI-IAM-MFA", "status": "partial"},
        ],
    }
    current = {
        "schema_version": "1.0",
        "report_type": "gap",
        "generated_at": "2026-04-28T12:00:00+00:00",
        "baseline_id": "fedramp-20x-moderate",
        "ksi_classifications": [
            {"ksi_id": "KSI-SVC-SNT", "status": "partial"},  # regressed
            {"ksi_id": "KSI-IAM-MFA", "status": "implemented"},  # improved
            {"ksi_id": "KSI-CMT-VTD", "status": "implemented"},  # added
        ],
    }
    diff = compute_gap_diff(prior, current)
    html = render_gap_diff_html(diff, **_kwargs())

    assert "Regressed (1)" in html
    assert "Improved (1)" in html
    assert "Added (1)" in html
    assert "KSI-SVC-SNT" in html
    assert "KSI-IAM-MFA" in html
    assert "KSI-CMT-VTD" in html
