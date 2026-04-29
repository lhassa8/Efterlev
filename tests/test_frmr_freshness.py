"""Tests for `check_catalog_freshness` — non-blocking init-time warnings."""

from __future__ import annotations

from datetime import date

from efterlev.frmr.freshness import (
    CR26_EXPECTED_AFTER,
    STALE_THRESHOLD_DAYS,
    check_catalog_freshness,
)
from efterlev.frmr.loader import FrmrDocument


def _doc(version: str = "0.9.43-beta", last_updated: str = "2026-04-08") -> FrmrDocument:
    return FrmrDocument(
        version=version,
        last_updated=last_updated,
        themes={},
        indicators={},
    )


def test_fresh_catalog_produces_no_warnings() -> None:
    # Catalog dated today; today right after the catalog. No warnings.
    doc = _doc(last_updated="2026-04-08")
    warnings = check_catalog_freshness(doc, today=date(2026, 4, 28))
    assert warnings == []


def test_catalog_older_than_threshold_triggers_stale_warning() -> None:
    # Catalog dated 2025-09-01; today 2026-04-28 → ~239 days old, past
    # the 180-day threshold.
    doc = _doc(last_updated="2025-09-01")
    warnings = check_catalog_freshness(doc, today=date(2026, 4, 28))
    assert len(warnings) == 1
    assert "239 days old" in warnings[0]
    assert "FedRAMP/docs" in warnings[0]


def test_catalog_at_threshold_boundary_does_not_warn() -> None:
    # Exactly STALE_THRESHOLD_DAYS old: no warning (the comparison is
    # strict greater-than, so exactly-180-days-old is acceptable).
    doc = _doc(last_updated="2026-01-01")
    today = date(2026, 1, 1) + __import__("datetime").timedelta(days=STALE_THRESHOLD_DAYS)
    warnings = check_catalog_freshness(doc, today=today)
    assert warnings == []


def test_catalog_one_day_past_threshold_warns() -> None:
    # Hold today before the CR26 window so we isolate the stale warning.
    # 181 days back from a date in 2026-04 is solidly pre-CR26.
    doc = _doc(last_updated="2025-10-29")
    today = date(2025, 10, 29) + __import__("datetime").timedelta(days=STALE_THRESHOLD_DAYS + 1)
    warnings = check_catalog_freshness(doc, today=today)
    stale_warnings = [w for w in warnings if "days old" in w]
    assert len(stale_warnings) == 1


def test_today_past_cr26_with_beta_catalog_warns() -> None:
    # Today is past CR26's expected window; vendored catalog still beta.
    # Both warnings can fire independently — this test isolates the CR26
    # warning by keeping the catalog "fresh" (within stale threshold).
    today = CR26_EXPECTED_AFTER.replace(day=CR26_EXPECTED_AFTER.day) + __import__(
        "datetime"
    ).timedelta(days=1)
    # Catalog dated within the stale threshold of `today` to suppress the
    # other warning.
    doc = _doc(
        version="0.9.50-beta",
        last_updated=(today.replace(month=max(1, today.month - 1))).isoformat(),
    )
    warnings = check_catalog_freshness(doc, today=today)
    cr26_warnings = [w for w in warnings if "CR26" in w]
    assert len(cr26_warnings) == 1
    assert "0.9.50-beta" in cr26_warnings[0]


def test_today_before_cr26_window_does_not_warn() -> None:
    # Today is before CR26's expected window even with a beta catalog.
    doc = _doc(version="0.9.43-beta")
    warnings = check_catalog_freshness(doc, today=date(2026, 4, 28))
    cr26_warnings = [w for w in warnings if "CR26" in w]
    assert cr26_warnings == []


def test_post_cr26_release_with_1x_catalog_does_not_warn() -> None:
    # Today is past the CR26 window but the catalog is no longer beta —
    # CR26 has shipped and Efterlev has bumped its vendored catalog.
    doc = _doc(version="1.0.0", last_updated="2026-07-15")
    today = date(2026, 7, 30)
    warnings = check_catalog_freshness(doc, today=today)
    cr26_warnings = [w for w in warnings if "CR26" in w]
    assert cr26_warnings == []


def test_malformed_last_updated_skips_stale_check_but_init_continues() -> None:
    # Defensive: a hand-edited catalog with a malformed `last_updated`
    # should NOT raise — the stale check skips silently. Init continues.
    doc = _doc(last_updated="not-a-date")
    warnings = check_catalog_freshness(doc, today=date(2026, 4, 28))
    # Stale check is skipped because the date doesn't parse; CR26 check
    # only runs if today is past the window, which 2026-04-28 isn't.
    assert warnings == []


def test_warnings_independent_can_both_fire() -> None:
    # Catalog is both stale and pre-CR26-naming, today is post-CR26 window.
    # Both warnings fire.
    doc = _doc(version="0.9.43-beta", last_updated="2026-01-01")
    today = date(2026, 8, 1)  # ~213 days past 2026-01-01 AND past 2026-06-30
    warnings = check_catalog_freshness(doc, today=today)
    assert len(warnings) == 2
    assert any("days old" in w for w in warnings)
    assert any("CR26" in w for w in warnings)
