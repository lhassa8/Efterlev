"""Catalog-path resolution and hash-verification tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from efterlev.errors import CatalogLoadError
from efterlev.paths import (
    EXPECTED_HASHES,
    vendored_catalogs_dir,
    verify_catalog_hashes,
)


def test_dev_install_resolves_repo_root_catalogs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EFTERLEV_CATALOGS_DIR", raising=False)
    resolved = vendored_catalogs_dir()
    # In this editable install, expect repo_root/catalogs (not site-packages).
    assert (resolved / "frmr" / "FRMR.documentation.json").is_file()
    assert (resolved / "nist" / "NIST_SP-800-53_rev5_catalog.json").is_file()


def test_env_override_is_honored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Build a minimal candidate dir with the marker file present.
    candidate = tmp_path / "my-catalogs"
    (candidate / "frmr").mkdir(parents=True)
    (candidate / "frmr" / "FRMR.documentation.json").write_text("{}")
    monkeypatch.setenv("EFTERLEV_CATALOGS_DIR", str(candidate))
    assert vendored_catalogs_dir() == candidate.resolve()


def test_env_override_rejects_missing_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EFTERLEV_CATALOGS_DIR", str(tmp_path))
    with pytest.raises(CatalogLoadError, match="does not contain"):
        vendored_catalogs_dir()


def test_verify_catalog_hashes_passes_on_vendored_files() -> None:
    # The repo-root vendored files MUST match the pinned hashes; any drift is a
    # provenance-chain failure and should surface immediately.
    catalogs = vendored_catalogs_dir()
    verify_catalog_hashes(catalogs)  # should not raise


def test_verify_catalog_hashes_raises_on_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Build a catalog-ish dir missing one of the expected files.
    source = vendored_catalogs_dir()
    shutil.copytree(source, tmp_path / "catalogs")
    (tmp_path / "catalogs" / "frmr" / "FRMR.md").unlink()
    with pytest.raises(CatalogLoadError, match="missing"):
        verify_catalog_hashes(tmp_path / "catalogs")


def test_verify_catalog_hashes_raises_on_content_drift(tmp_path: Path) -> None:
    source = vendored_catalogs_dir()
    shutil.copytree(source, tmp_path / "catalogs")
    (tmp_path / "catalogs" / "frmr" / "FRMR.md").write_text("tampered")
    with pytest.raises(CatalogLoadError, match="SHA-256 mismatch"):
        verify_catalog_hashes(tmp_path / "catalogs")


def test_expected_hashes_cover_vendored_tree() -> None:
    # Sanity: every file EXPECTED_HASHES names actually exists in the vendored
    # catalogs directory. This catches the case where a path string in
    # EXPECTED_HASHES gets stale (different from what we ship).
    catalogs = vendored_catalogs_dir()
    for rel in EXPECTED_HASHES:
        assert (catalogs / rel).is_file(), f"expected file {rel} not in {catalogs}"
