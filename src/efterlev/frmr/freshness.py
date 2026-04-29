"""FRMR catalog freshness checks emitted at `efterlev init` time.

The vendored catalog at `catalogs/frmr/FRMR.documentation.json` is hash-pinned
by `verify_catalog_hashes`, so users cannot accidentally drift its content.
What the hash check cannot tell them is whether *the upstream catalog* has
moved on past what Efterlev vendored. Two heuristics fire at init:

  1. **Stale by elapsed time.** If today is more than 180 days past the
     catalog's `last_updated`, print a soft warning. FedRAMP publishes
     incremental revisions every couple of months in the v0.9.x stream;
     a 6-month gap is a strong "you may be behind" signal.

  2. **Past CR26 release window.** CR26 (Consolidated Rules 2026) is the
     next major FedRAMP catalog revision. The published timeline calls
     for a release in mid-2026 with effect Dec 31, 2026. If today is
     past 2026-06-30 and the vendored catalog version still starts
     with "0." (i.e. pre-CR26 numbering), warn that CR26 may have
     shipped and an Efterlev upgrade is in order.

Both warnings are non-blocking; init proceeds. The warnings flow to the
caller as a list of strings; `init_workspace` returns them on the
`InitResult` and the CLI emits each to stderr.

Reasoning about thresholds: the 180-day window and the 2026-06-30 date
are tuned for v0.1.x. As Efterlev ships new releases that bump the
vendored catalog, the gap stays small for fresh installs; the warnings
fire on installs that have not been refreshed in 6+ months. CR26's date
is best-effort per FedRAMP's published timeline; if FedRAMP slips, the
warning fires false-positively but harmlessly. The constants live in
this module rather than config so they update with each Efterlev
release rather than with each customer's local config.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from efterlev.frmr.loader import FrmrDocument

# How old can the vendored catalog be before we nudge the user?
# 180 days is roughly two FedRAMP review cycles; long enough to avoid
# nuisance warnings on fresh installs, short enough to flag genuinely
# stale deployments.
STALE_THRESHOLD_DAYS = 180

# CR26 (Consolidated Rules 2026) expected-release window per FedRAMP's
# 2026-04 announcements. Past this date with a beta-version catalog,
# warn that the upstream may have shipped a major revision.
CR26_EXPECTED_AFTER = date(2026, 6, 30)


def check_catalog_freshness(
    frmr_doc: FrmrDocument,
    today: date | None = None,
) -> list[str]:
    """Return zero or more freshness warnings for the loaded FRMR document.

    `today` is injectable for tests; production callers leave it as None
    and the function uses `date.today()`. Each returned string is a
    full warning ready to print to stderr — the caller is responsible
    only for emission.
    """
    if today is None:
        today = date.today()

    warnings: list[str] = []

    # last_updated is "YYYY-MM-DD"; FRMR has used this format consistently
    # since v0.9.0-beta. Parse defensively — a malformed string skips the
    # elapsed-time check rather than tripping init.
    try:
        last_updated = datetime.strptime(frmr_doc.last_updated, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        last_updated = None

    if last_updated is not None:
        days_old = (today - last_updated).days
        if days_old > STALE_THRESHOLD_DAYS:
            warnings.append(
                f"warning: vendored FRMR catalog (v{frmr_doc.version}, "
                f"dated {frmr_doc.last_updated}) is {days_old} days old. "
                f"Check https://github.com/FedRAMP/docs/blob/main/FRMR.documentation.json "
                f"for newer revisions, or upgrade Efterlev to a release that vendors "
                f"the latest catalog."
            )

    # CR26 awareness check. Fire when today is past the expected window
    # AND the vendored version still uses pre-CR26 numbering (starts with
    # "0."). CR26 will likely bump the major to 1.x.
    if today > CR26_EXPECTED_AFTER and frmr_doc.version.startswith("0."):
        warnings.append(
            f"warning: today ({today.isoformat()}) is past the CR26 "
            f"(Consolidated Rules 2026) expected release window "
            f"({CR26_EXPECTED_AFTER.isoformat()}). The vendored FRMR catalog "
            f"is still beta-version '{frmr_doc.version}'. If CR26 has shipped, "
            f"upgrade Efterlev to pick up the new catalog; check "
            f"https://github.com/FedRAMP/docs for the current state."
        )

    return warnings
