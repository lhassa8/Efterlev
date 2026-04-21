"""OSCAL 800-53 loader tests against the vendored `catalogs/nist/` file.

The vendored NIST catalog is SP 800-53 Rev 5.2.0; tests assert on the known
structure (20 families, 324 top-level controls, 1,196 total incl.
enhancements) verified by `scripts/trestle_smoke.py` pre-hackathon.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from efterlev.errors import CatalogLoadError
from efterlev.models import Control, ControlEnhancement
from efterlev.oscal import OscalCatalog, load_oscal_800_53

NIST_CATALOG = (
    Path(__file__).resolve().parents[1] / "catalogs" / "nist" / "NIST_SP-800-53_rev5_catalog.json"
)


@pytest.fixture(scope="module")
def cat() -> OscalCatalog:
    """Module-scoped: one trestle load shared by the 4 tests that need it.

    A fresh load takes ~9s because the catalog is 10MB of OSCAL JSON and
    trestle does a full Pydantic parse. Sharing across the read-only tests
    keeps the overall suite under 15s.
    """
    return load_oscal_800_53(NIST_CATALOG)


def test_loads_vendored_nist_catalog(cat: OscalCatalog) -> None:
    assert isinstance(cat, OscalCatalog)
    assert len(cat.controls) == 324
    # All six of our hackathon detection areas resolve as top-level controls.
    for cid in ["sc-28", "sc-8", "sc-13", "ia-2", "au-2", "au-12", "cp-9"]:
        assert cid in cat.controls, f"{cid} missing from vendored 800-53 catalog"


def test_sc_28_has_known_enhancement_and_family(cat: OscalCatalog) -> None:
    sc_28 = cat.controls["sc-28"]
    assert sc_28.family == "sc"
    enh_ids = {e.id for e in sc_28.enhancements}
    # SC-28(1) "Cryptographic Protection" is in every Rev 5 release to date.
    assert "sc-28.1" in enh_ids


def test_lookup_finds_controls_and_enhancements(cat: OscalCatalog) -> None:
    top = cat.lookup("sc-28")
    assert isinstance(top, Control)
    enh = cat.lookup("sc-28.1")
    assert isinstance(enh, ControlEnhancement)
    assert enh.parent_id == "sc-28"
    assert cat.lookup("not-a-real-control-id") is None


def test_total_enhancement_count_matches_expected_for_rev5_2_0(cat: OscalCatalog) -> None:
    # 1196 total controls incl. enhancements; 324 are top-level, so 872 enh.
    assert len(cat.enhancements_by_id) == 1196 - 324


def test_missing_file_raises_catalog_load_error(tmp_path: Path) -> None:
    with pytest.raises(CatalogLoadError, match="failed to load OSCAL catalog"):
        load_oscal_800_53(tmp_path / "nonexistent.json")
