# Models reference

Stub for SPEC-38.13. Auto-generation via `mkdocstrings` is queued for a follow-up batch.

For the current authoritative reference, see the Pydantic models in:

- `src/efterlev/models/source.py` — `TerraformResource`, `SourceRef`.
- `src/efterlev/models/evidence.py` — `Evidence`.
- `src/efterlev/models/claim.py` — `Claim`.
- `src/efterlev/models/manifest.py` — `EvidenceManifest`, `ManifestAttestation`.
- `src/efterlev/models/attestation.py` — `AttestationDraft`, `AttestationArtifact`.
- `src/efterlev/models/poam.py` — `PoamClassificationInput`.
- `src/efterlev/provenance/store.py` — `ProvenanceRecord`.

All models use `extra="forbid"` and immutable `frozen=True` configs by default. Every Claim carries `requires_review: Literal[True]` enforced at the type level.
