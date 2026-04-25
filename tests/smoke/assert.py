#!/usr/bin/env python3
"""Smoke-test assertion: verify `efterlev scan` produced a valid store.

Called by .github/workflows/release-smoke.yml after the scan step in
every matrix cell. Checks that the install produced a real, valid
Efterlev state, not just "exit 0 from somewhere."

Usage:
    python3 tests/smoke/assert.py <store-dir>

Exits 0 on success, 1 on any failure. Prints a short human-readable
summary on both paths.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <store-dir>", file=sys.stderr)
        return 1

    store_dir = Path(sys.argv[1])
    failures: list[str] = []
    html_count = 0
    evidence_count = 0

    if not store_dir.is_dir():
        failures.append(f"store dir {store_dir} does not exist")

    db_path = store_dir / "store.db"
    if not db_path.is_file():
        failures.append(f"SQLite DB missing at {db_path}")

    reports_dir = store_dir / "reports"
    if reports_dir.is_dir():
        html_count = len(list(reports_dir.glob("*.html")))
        if html_count == 0:
            failures.append(f"no HTML reports in {reports_dir}")
    else:
        failures.append(f"reports dir missing at {reports_dir}")

    if db_path.is_file():
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.execute(
                "SELECT COUNT(*) FROM records WHERE record_type = 'evidence'"
            )
            (evidence_count,) = cur.fetchone()
            if evidence_count == 0:
                failures.append("no evidence records in store")
        except sqlite3.Error as e:
            failures.append(f"sqlite error querying store: {e}")

    print(
        f"Smoke assertion state: "
        f"store_dir={store_dir.is_dir()}, "
        f"db={db_path.is_file()}, "
        f"html_reports={html_count}, "
        f"evidence_records={evidence_count}"
    )

    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
