"""Smoke test for compliance-trestle OSCAL parsing.

Loads the vendored NIST SP 800-53 Rev 5 catalog via trestle's Pydantic models and
prints metadata + a recursive control count. Used once pre-hackathon to confirm the
Python 3.12 install of compliance-trestle can round-trip a real OSCAL artifact.

Run: `uv run python scripts/trestle_smoke.py`
"""

from __future__ import annotations

from pathlib import Path

from trestle.oscal.catalog import Catalog, Control

CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalogs" / "nist" / "NIST_SP-800-53_rev5_catalog.json"


def count_controls(controls: list[Control] | None) -> tuple[int, int]:
    """Return (top_level_count, total_including_enhancements) for a control list."""
    if not controls:
        return 0, 0
    top = len(controls)
    total = top
    for c in controls:
        _, sub = count_controls(c.controls)
        total += sub
    return top, total


def main() -> None:
    if not CATALOG_PATH.exists():
        raise SystemExit(f"catalog not found: {CATALOG_PATH}")
    catalog = Catalog.oscal_read(CATALOG_PATH)
    md = catalog.metadata
    print(f"file:          {CATALOG_PATH.relative_to(Path.cwd())}")
    print(f"bytes:         {CATALOG_PATH.stat().st_size:,}")
    print(f"title:         {md.title}")
    print(f"version:       {md.version}")
    print(f"oscal-version: {md.oscal_version}")
    print(f"published:     {md.published}")
    print(f"groups:        {len(catalog.groups or [])}")

    grand_top = 0
    grand_total = 0
    for group in catalog.groups or []:
        top, total = count_controls(group.controls)
        grand_top += top
        grand_total += total
        print(f"  {group.id:<8} {group.title:<40} top={top:>3}  total={total:>4}")
    print(f"total top-level controls:             {grand_top}")
    print(f"total controls including enhancements: {grand_total}")


if __name__ == "__main__":
    main()
