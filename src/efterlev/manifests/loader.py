"""Read and validate `.efterlev/manifests/*.yml` into `EvidenceManifest`.

The loader is intentionally separate from the primitive that emits Evidence.
It handles file discovery, YAML parsing, and Pydantic validation. The
`load_evidence_manifests` primitive in `efterlev.primitives.evidence`
orchestrates the loader, resolves KSI-to-controls mappings from the loaded
FRMR document, builds Evidence records, and persists them to the store.

Errors raise `ManifestError` with the offending file path included so a
customer editing a manifest can find and fix the bad file immediately.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from efterlev.errors import ManifestError
from efterlev.models.manifest import EvidenceManifest

_MANIFEST_GLOBS = ("*.yml", "*.yaml")


def discover_manifest_files(manifest_dir: Path) -> list[Path]:
    """Return every `*.yml` / `*.yaml` file under the manifest dir, sorted.

    Returns an empty list if the directory does not exist — a repo without
    any manifests is a valid state (the customer has declared no procedural
    attestations yet). Sorting is deterministic so provenance walks and
    test assertions see the same order across runs.
    """
    if not manifest_dir.is_dir():
        return []
    files: set[Path] = set()
    for pattern in _MANIFEST_GLOBS:
        files.update(manifest_dir.glob(pattern))
    return sorted(files)


def load_manifest_file(path: Path) -> EvidenceManifest:
    """Parse and validate a single manifest YAML file.

    Raises `ManifestError` on:
      - I/O error reading the file
      - YAML syntax error
      - Pydantic validation failure (missing required fields, unknown keys
        under `extra="forbid"`, malformed dates)
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ManifestError(f"failed to read manifest at {path}: {e}") from e

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ManifestError(f"manifest at {path} is not valid YAML: {e}") from e

    if not isinstance(data, dict):
        raise ManifestError(
            f"manifest at {path} must be a YAML mapping at the top level; got {type(data).__name__}"
        )

    try:
        return EvidenceManifest.model_validate(data)
    except ValidationError as e:
        raise ManifestError(f"manifest at {path} failed schema validation: {e}") from e
