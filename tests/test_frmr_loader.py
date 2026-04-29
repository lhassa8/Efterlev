"""FRMR loader tests against the vendored `catalogs/frmr/` files.

The vendored FRMR version is 0.9.43-beta (2026-04-08); tests assert on the
known structure of that snapshot. When `catalogs/frmr/` is bumped, update
these expectations (or pull them from the loaded doc rather than hardcoding).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from efterlev.errors import CatalogLoadError
from efterlev.frmr import FrmrDocument, load_frmr

VENDORED = Path(__file__).resolve().parents[1] / "catalogs" / "frmr"
FRMR_PATH = VENDORED / "FRMR.documentation.json"
SCHEMA_PATH = VENDORED / "FedRAMP.schema.json"


def test_loads_vendored_frmr_without_schema() -> None:
    doc = load_frmr(FRMR_PATH)
    assert isinstance(doc, FrmrDocument)
    assert doc.version == "0.9.43-beta"
    assert doc.last_updated == "2026-04-08"
    assert len(doc.themes) == 11
    assert len(doc.indicators) == 60


def test_loads_vendored_frmr_against_schema() -> None:
    doc = load_frmr(FRMR_PATH, schema_path=SCHEMA_PATH)
    # Schema validation is a strict gate; if this passes, the vendored FRMR
    # agrees with its own schema and the loader's validator integration works.
    assert doc.version == "0.9.43-beta"


def test_expected_ksi_svc_snt_resolves_with_expected_controls() -> None:
    doc = load_frmr(FRMR_PATH)
    snt = doc.indicators["KSI-SVC-SNT"]
    assert snt.theme == "SVC"
    assert snt.name == "Securing Network Traffic"
    assert "sc-8" in snt.controls
    assert "sc-13" in snt.controls


def test_theme_svc_carries_description() -> None:
    doc = load_frmr(FRMR_PATH)
    svc = doc.themes["SVC"]
    assert svc.id == "SVC"
    assert svc.name == "Service Configuration"
    # Every KSI theme in 0.9.43-beta has a theme-level description paragraph.
    assert svc.description is not None
    assert len(svc.description) > 0


def test_every_indicator_has_a_parent_theme_entry() -> None:
    doc = load_frmr(FRMR_PATH)
    for ind in doc.indicators.values():
        assert ind.theme in doc.themes, f"indicator {ind.id} references unknown theme {ind.theme}"


def test_missing_file_raises_catalog_load_error(tmp_path: Path) -> None:
    with pytest.raises(CatalogLoadError, match="failed to read"):
        load_frmr(tmp_path / "nonexistent.json")


def test_malformed_json_raises_catalog_load_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    with pytest.raises(CatalogLoadError, match="not valid JSON"):
        load_frmr(bad)


def test_missing_required_top_level_key_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"info": {"version": "x", "last_updated": "y"}}))  # no KSI
    with pytest.raises(CatalogLoadError, match="missing required key"):
        load_frmr(bad)


def test_schema_mismatch_raises_with_pointer(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"oops": "wrong shape"}))
    with pytest.raises(CatalogLoadError, match="schema validation"):
        load_frmr(bad, schema_path=SCHEMA_PATH)


def test_loader_picks_up_per_level_statement_from_varies_by_level() -> None:
    # In FRMR 0.9.43-beta, 5 KSIs (CNA-EIS, MLA-ALA, SVC-PRR, SVC-RUD,
    # SVC-VCM) keep their statement under varies_by_level.{level}.statement
    # rather than at the top level. Without this fallback, the Gap Agent
    # sees no statement and classifies them as evidence_layer_inapplicable
    # for the wrong reason. Lock in the fix at moderate level.
    doc = load_frmr(FRMR_PATH, level="moderate")
    for ksi_id in (
        "KSI-CNA-EIS",
        "KSI-MLA-ALA",
        "KSI-SVC-PRR",
        "KSI-SVC-RUD",
        "KSI-SVC-VCM",
    ):
        ind = doc.indicators[ksi_id]
        assert ind.statement is not None and len(ind.statement) > 0, (
            f"{ksi_id} statement is empty after loader read; varies_by_level lookup is broken"
        )


def test_loader_falls_back_to_top_level_statement_when_no_level_path(
    tmp_path: Path,
) -> None:
    # Catalogs that haven't migrated to varies_by_level should still load.
    legacy = tmp_path / "legacy_frmr.json"
    legacy.write_text(
        json.dumps(
            {
                "info": {"version": "test", "last_updated": "2026-01-01"},
                "KSI": {
                    "TST": {
                        "name": "Test theme",
                        "indicators": {
                            "KSI-TST-001": {
                                "name": "Top-level statement",
                                "statement": "this is at the top level",
                                "controls": [],
                            },
                        },
                    },
                },
            }
        )
    )
    doc = load_frmr(legacy, level="moderate")
    assert doc.indicators["KSI-TST-001"].statement == "this is at the top level"


def test_loader_prefers_level_statement_over_top_level_when_both_present(
    tmp_path: Path,
) -> None:
    # If a catalog ever carries both a top-level and a per-level statement,
    # the per-level one wins (consistent with FRMR's "varies_by_level"
    # being the authoritative location for impact-specific text).
    mixed = tmp_path / "mixed_frmr.json"
    mixed.write_text(
        json.dumps(
            {
                "info": {"version": "test", "last_updated": "2026-01-01"},
                "KSI": {
                    "TST": {
                        "name": "Test theme",
                        "indicators": {
                            "KSI-TST-001": {
                                "name": "Both statements",
                                "statement": "the legacy top-level one",
                                "varies_by_level": {"moderate": {"statement": "the moderate one"}},
                                "controls": [],
                            },
                        },
                    },
                },
            }
        )
    )
    doc = load_frmr(mixed, level="moderate")
    assert doc.indicators["KSI-TST-001"].statement == "the moderate one"
