"""Evidence primitives — surfacing evidence from non-scanner sources.

The first primitive here is `load_evidence_manifests`, which reads
human-signed procedural attestations from `.efterlev/manifests/*.yml` and
emits them as `Evidence` records with `detector_id="manifest"`. Future
evidence primitives (runtime-API Evidence via boto3, archived-scan import,
external-audit-result import) live alongside.

Importing this package triggers primitive registration via the `@primitive`
decorator on each module below.
"""

from __future__ import annotations

from efterlev.primitives.evidence.load_evidence_manifests import (
    MANIFEST_DETECTOR_ID,
    LoadEvidenceManifestsInput,
    LoadEvidenceManifestsOutput,
    ManifestLoadSummary,
    load_evidence_manifests,
)

__all__ = [
    "MANIFEST_DETECTOR_ID",
    "LoadEvidenceManifestsInput",
    "LoadEvidenceManifestsOutput",
    "ManifestLoadSummary",
    "load_evidence_manifests",
]
