"""`init_workspace` end-to-end tests.

These load the real vendored catalogs (one trestle parse per test file, since
`init_workspace` doesn't currently accept a pre-loaded catalog). Kept to two
tests that exercise the happy path + the exists/force flow; CLI-level
integration tests live in `test_cli.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from efterlev.config import load_config
from efterlev.errors import ConfigError
from efterlev.provenance import ProvenanceStore, walk_chain
from efterlev.workspace import init_workspace


def test_init_workspace_creates_everything_a_scan_needs(tmp_path: Path) -> None:
    result = init_workspace(tmp_path, "fedramp-20x-moderate")

    assert result.efterlev_dir == tmp_path / ".efterlev"
    assert (tmp_path / ".efterlev").is_dir()
    assert (tmp_path / ".efterlev" / "config.toml").is_file()
    assert (tmp_path / ".efterlev" / "cache" / "frmr_document.json").is_file()
    assert (tmp_path / ".efterlev" / "cache" / "oscal_catalog.json").is_file()
    assert (tmp_path / ".efterlev" / "store.db").is_file()
    assert (tmp_path / ".efterlev" / "receipts.log").is_file()

    # Config round-trips to the expected baseline.
    cfg = load_config(tmp_path / ".efterlev" / "config.toml")
    assert cfg.baseline.id == "fedramp-20x-moderate"

    # Known FRMR and 800-53 shape.
    assert result.frmr_version == "0.9.43-beta"
    assert result.num_indicators == 60
    assert result.num_themes == 11
    assert result.num_controls == 324

    # The init writes a provenance load-receipt walkable via the existing
    # `efterlev provenance show` plumbing.
    with ProvenanceStore(tmp_path) as store:
        chain = walk_chain(store, result.receipt_record_id)
    assert chain.record.record_type == "evidence"
    assert chain.record.primitive == "efterlev.init@0.1.0"
    assert chain.parents == []  # raw evidence, no parents


def test_init_refuses_when_efterlev_already_exists(tmp_path: Path) -> None:
    init_workspace(tmp_path, "fedramp-20x-moderate")
    with pytest.raises(ConfigError, match="already exists"):
        init_workspace(tmp_path, "fedramp-20x-moderate")


def test_init_with_force_overwrites(tmp_path: Path) -> None:
    first = init_workspace(tmp_path, "fedramp-20x-moderate")
    second = init_workspace(tmp_path, "fedramp-20x-moderate", force=True)
    # Same workspace; the two receipts are distinct records in the same store.
    assert first.receipt_record_id != second.receipt_record_id


def test_init_rejects_unsupported_baseline(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not supported at v0"):
        init_workspace(tmp_path, "fedramp-high")
