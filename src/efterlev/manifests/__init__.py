"""Evidence Manifest loader — reads `.efterlev/manifests/*.yml`.

Manifest files declare human-signed procedural attestations that produce
`Evidence` records alongside detector-emitted Evidence. The loader in
`efterlev.manifests.loader` handles file discovery, YAML parsing, and
Pydantic schema validation; the `load_evidence_manifests` primitive in
`efterlev.primitives.evidence` is the agent-legible entry point that
materializes manifests into Evidence and persists them.

See `efterlev.models.manifest` for the YAML shape and DECISIONS 2026-04-22
for the design rationale.
"""

from __future__ import annotations

from efterlev.manifests.loader import (
    discover_manifest_files,
    load_manifest_file,
)

__all__ = ["discover_manifest_files", "load_manifest_file"]
