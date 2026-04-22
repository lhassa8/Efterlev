"""`load_evidence_manifests` primitive — load manifest YAMLs into Evidence.

Reads every `.efterlev/manifests/*.yml` under the provided directory, parses
each into an `EvidenceManifest` via the loader, and emits one `Evidence`
per attestation with `detector_id="manifest"`. Every emitted Evidence is
persisted to the active provenance store (tagged with the primitive name)
so each attestation is individually citable in a provenance walk — mirroring
the per-Evidence persistence pattern the `@detector` decorator applies to
scanner output.

Controls resolution: the caller passes `ksi_to_controls` derived from the
loaded FRMR document. For a manifest whose KSI is not present in that
mapping (e.g. a KSI deprecated in the current baseline, or a typo), the
primitive records the skip in `skipped_unknown_ksi` and logs a warning —
it does NOT fabricate a control list or invent a KSI.

Supporting-docs handling: URLs and local paths are preserved as opaque
strings in Evidence.content.supporting_docs. No fetching, no hashing, no
existence check at v0 Phase 1 — supporting docs are pointers the 3PAO
follows manually. Hashing + snapshotting into the blob store is a Phase 5
enhancement (signed attestation chain).

Freshness: `next_review` is preserved in Evidence.content, and an
`is_stale: bool` convenience flag is set when `next_review < today`. Full
staleness treatment at the Gap Agent prompt layer is Phase 5 scope per the
2026-04-22 DECISIONS entry; Phase 1 just surfaces the data.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from efterlev.manifests import discover_manifest_files, load_manifest_file
from efterlev.models import Evidence, SourceRef
from efterlev.models.manifest import EvidenceManifest, ManifestAttestation
from efterlev.primitives.base import primitive
from efterlev.provenance.context import get_active_store

log = logging.getLogger(__name__)

MANIFEST_DETECTOR_ID = "manifest"
MANIFEST_PRIMITIVE_VERSION = "0.1.0"


class LoadEvidenceManifestsInput(BaseModel):
    """Input to `load_evidence_manifests`.

    `manifest_dir` is typically `<repo-root>/.efterlev/manifests/`.
    `ksi_to_controls` comes from the loaded FRMR document and is used to
    populate `Evidence.controls_evidenced` without duplicating the mapping
    in the YAML files (single source of truth: FRMR).
    """

    model_config = ConfigDict(frozen=True)

    manifest_dir: Path
    ksi_to_controls: dict[str, list[str]]


class ManifestLoadSummary(BaseModel):
    """One manifest file's contribution to a load call."""

    model_config = ConfigDict(frozen=True)

    file: Path
    ksi: str
    attestation_count: int


class LoadEvidenceManifestsOutput(BaseModel):
    """Structured summary of a manifest load, with evidence for downstream use."""

    model_config = ConfigDict(frozen=True)

    files_found: int
    manifests_loaded: int
    evidence: list[Evidence] = Field(default_factory=list)
    per_manifest: list[ManifestLoadSummary] = Field(default_factory=list)
    skipped_unknown_ksi: list[str] = Field(default_factory=list)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)


@primitive(capability="evidence", side_effects=False, version="0.1.0", deterministic=True)
def load_evidence_manifests(
    input: LoadEvidenceManifestsInput,
) -> LoadEvidenceManifestsOutput:
    """Discover, parse, and materialize manifest YAMLs into Evidence records.

    One Evidence per attestation block. Per-Evidence persistence is inline
    (one `store.write_record` per attestation, tagged with the primitive's
    spec_name) so each attestation is a standalone node in the provenance
    graph and can be cited by `evidence_id`. The `@primitive` wrapper
    additionally writes a single summary record for the call itself; the
    two record classes are separated by payload shape exactly as
    `scan_terraform` + `@detector` separates them.
    """
    files = discover_manifest_files(input.manifest_dir)
    now = datetime.now(UTC)
    primitive_spec_name = f"{load_evidence_manifests.__name__}@{MANIFEST_PRIMITIVE_VERSION}"
    evidence: list[Evidence] = []
    per_manifest: list[ManifestLoadSummary] = []
    skipped: list[str] = []
    loaded = 0

    store = get_active_store()

    for path in files:
        manifest = load_manifest_file(path)
        if manifest.ksi not in input.ksi_to_controls:
            log.warning(
                "manifest %s declares KSI %s which is not in the loaded baseline; skipping",
                path,
                manifest.ksi,
            )
            skipped.append(manifest.ksi)
            continue

        controls = input.ksi_to_controls[manifest.ksi]
        for attestation in manifest.evidence:
            ev = _build_evidence(
                manifest=manifest,
                attestation=attestation,
                manifest_path=path,
                controls=controls,
                now=now,
            )
            evidence.append(ev)
            if store is not None:
                store.write_record(
                    payload=ev.model_dump(mode="json"),
                    record_type="evidence",
                    primitive=primitive_spec_name,
                )

        loaded += 1
        per_manifest.append(
            ManifestLoadSummary(
                file=path,
                ksi=manifest.ksi,
                attestation_count=len(manifest.evidence),
            )
        )

    if store is None and files:
        log.warning(
            "load_evidence_manifests found %d manifest(s) but no active provenance "
            "store; evidence returned in-memory only (ad-hoc use is ok; production "
            "must activate a store)",
            len(files),
        )

    # Dedupe skipped KSIs while preserving first-seen order. Two manifest files
    # referencing the same unknown KSI should surface as one entry in the
    # output, not two.
    seen: set[str] = set()
    skipped_unique: list[str] = []
    for ksi in skipped:
        if ksi not in seen:
            seen.add(ksi)
            skipped_unique.append(ksi)

    return LoadEvidenceManifestsOutput(
        files_found=len(files),
        manifests_loaded=loaded,
        evidence=evidence,
        per_manifest=per_manifest,
        skipped_unknown_ksi=skipped_unique,
    )


def _build_evidence(
    *,
    manifest: EvidenceManifest,
    attestation: ManifestAttestation,
    manifest_path: Path,
    controls: list[str],
    now: datetime,
) -> Evidence:
    """Assemble one Evidence record from a manifest attestation block."""
    is_stale = attestation.next_review is not None and attestation.next_review < now.date()
    content: dict[str, Any] = {
        "type": attestation.type,
        "statement": attestation.statement,
        "attested_by": attestation.attested_by,
        "attested_at": attestation.attested_at.isoformat(),
        "reviewed_at": attestation.reviewed_at.isoformat() if attestation.reviewed_at else None,
        "next_review": attestation.next_review.isoformat() if attestation.next_review else None,
        "supporting_docs": list(attestation.supporting_docs),
        "manifest_name": manifest.name,
        "is_stale": is_stale,
    }
    return Evidence.create(
        detector_id=MANIFEST_DETECTOR_ID,
        ksis_evidenced=[manifest.ksi],
        controls_evidenced=list(controls),
        source_ref=SourceRef(file=manifest_path),
        content=content,
        timestamp=now,
    )
