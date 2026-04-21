"""Filesystem paths for the vendored FRMR + 800-53 catalogs and expected hashes.

Resolving the catalogs directory handles three installation shapes:

  1. Editable / development install (`pip install -e .`): the repo's source tree
     is the package. `catalogs/` lives at the repo root, sibling to `src/`.
  2. Wheel install (`pipx install efterlev`): the `pyproject.toml` force-include
     copies `catalogs/` to `efterlev/catalogs/` inside the installed package.
  3. Explicit override: `EFTERLEV_CATALOGS_DIR=/some/path` trumps both, for
     users pointing at a locally-updated catalog set (M9 in DECISIONS
     2026-04-20 deferred the full override flag to later; the env var gives
     the same flexibility today without a new CLI option).

`EXPECTED_HASHES` mirrors the provenance table in `catalogs/README.md`. When
catalogs bump, both are updated together; `efterlev init` verifies the on-
disk files match these hashes and records a load receipt so drift is visible.
"""

from __future__ import annotations

import hashlib
import os
from importlib.resources import files
from pathlib import Path

from efterlev.errors import CatalogLoadError

# Per catalogs/README.md provenance table (2026-04-19). Update here when bumped.
EXPECTED_HASHES: dict[str, str] = {
    "frmr/FRMR.documentation.json": (
        "bbb734e9acb5a7ad48dafd6b2f442178f2b507c78c46b897cc4b1852c746c7c4"
    ),
    "frmr/FRMR.md": ("43aa72808f63d5e49055f47434ee273654cb09fe80b0e5eb02401a02dc9f1e8d"),
    "frmr/FedRAMP.schema.json": (
        "1301497c55c6c188b8ba6c1236dc2d7c73286b55dc2ca5e6013ad38f0ba75f0c"
    ),
    "nist/NIST_SP-800-53_rev5_catalog.json": (
        "1645df6a370dcb931db2e2d5d70c2f77bc89c38499a416c23a70eb2c0e595bcc"
    ),
}

_MARKER = "frmr/FRMR.documentation.json"


def _contains_marker(candidate: Path) -> bool:
    return (candidate / _MARKER).is_file()


def vendored_catalogs_dir() -> Path:
    """Return the directory containing the vendored FRMR + NIST catalogs.

    Raises `CatalogLoadError` if no candidate location contains a recognizable
    FRMR file. Callers should treat this as a configuration / packaging error
    and instruct the user to reinstall or set `EFTERLEV_CATALOGS_DIR`.
    """
    override = os.environ.get("EFTERLEV_CATALOGS_DIR")
    if override:
        path = Path(override).resolve()
        if _contains_marker(path):
            return path
        raise CatalogLoadError(f"EFTERLEV_CATALOGS_DIR={override!r} does not contain {_MARKER}")

    # Dev / editable install: walk up from this module looking for repo-root catalogs/.
    current = Path(__file__).resolve().parent
    for parent in [*current.parents]:
        candidate = parent / "catalogs"
        if _contains_marker(candidate):
            return candidate

    # Wheel install: force-included under the package.
    try:
        packaged = Path(str(files("efterlev") / "catalogs"))
        if _contains_marker(packaged):
            return packaged
    except (ModuleNotFoundError, FileNotFoundError):
        pass

    raise CatalogLoadError(
        "cannot locate vendored catalogs/. Reinstall Efterlev or set "
        "EFTERLEV_CATALOGS_DIR to the directory holding frmr/ and nist/."
    )


def resolve_within_root(candidate: Path, root: Path) -> Path | None:
    """Resolve `candidate` against `root`, rejecting any path that escapes it.

    Used by the Remediation Agent / CLI to safely read `.tf` files referenced
    by `Evidence.source_ref.file`. Evidence could in principle contain a
    traversal payload (`../../../etc/passwd`) — a malicious detector, a
    corrupted store, or a hand-edited blob could smuggle one in. This helper
    joins `candidate` onto `root`, fully resolves symlinks, and verifies the
    result is still under the resolved `root`. Returns the resolved path on
    success, `None` on any attempted escape.

    `candidate` may be absolute or relative. Both are treated the same way:
    resolve against `root`, then check containment. Absolute paths that
    happen to live inside `root` are accepted — the Terraform parser captures
    source_ref.file paths exactly as they were walked at scan time, which in
    CI is absolute (e.g. `/home/runner/work/repo/infra/terraform/main.tf`).
    Rejecting those on principle broke the remediation flow; containment is
    the real safety check. Absolute paths outside `root` (`/etc/passwd`,
    `../../../secrets`) still fail containment and are rejected.
    """
    resolved_root = root.resolve()
    try:
        # When `candidate` is absolute, `resolved_root / candidate` ignores
        # `resolved_root` and yields `candidate`. When it's relative, the
        # two are joined. Both paths then go through `.resolve()` to
        # normalize symlinks and `..` segments before the containment check.
        full = (resolved_root / candidate).resolve()
        # relative_to raises ValueError if `full` isn't under `resolved_root`.
        full.relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    return full


def verify_catalog_hashes(catalogs_dir: Path) -> None:
    """Hash every file named in EXPECTED_HASHES under `catalogs_dir`.

    Raises `CatalogLoadError` on the first mismatch or missing file. On
    success, returns None — callers interpret that as "every vendored file is
    exactly the bytes we pinned."
    """
    for rel, expected in EXPECTED_HASHES.items():
        path = catalogs_dir / rel
        if not path.is_file():
            raise CatalogLoadError(f"vendored catalog file missing: {path}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise CatalogLoadError(
                f"SHA-256 mismatch for {rel}: expected {expected}, got {actual}. "
                "Either the vendored file was tampered with, or the expected "
                "hash in src/efterlev/paths.py is out of date (check against "
                "catalogs/README.md)."
            )
