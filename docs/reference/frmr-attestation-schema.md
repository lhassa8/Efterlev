# FRMR attestation schema

Stub for SPEC-38.13. Schema documentation is queued for a follow-up batch.

The Documentation Agent emits an FRMR-compatible JSON artifact at `.efterlev/reports/attestation-<timestamp>.json` per scan. The shape is:

```json
{
  "info": {
    "version": "0.9.43-beta",
    "baseline": "fedramp-20x-moderate",
    "generated_at": "2026-04-25T14:00:00Z",
    "draft": true
  },
  "KSI": {
    "<theme>": {
      "<KSI-id>": {
        "status": "implemented | partial | not_implemented | not_applicable",
        "narrative": "...",
        "evidence_ids": ["sha256:..."]
      }
    }
  },
  "provenance": {
    "scan_record_id": "sha256:...",
    "agent_record_ids": ["sha256:..."]
  }
}
```

The Pydantic source of truth: `AttestationArtifact` in `src/efterlev/models/attestation.py`. `extra="forbid"`, every Claim carries `requires_review=Literal[True]`.

This is FRMR-inspired but NOT a valid FRMR *catalog* — FedRAMP has not yet published an attestation-output schema. When they do, Efterlev migrates. See [`DECISIONS.md` 2026-04-22 "Phase 2: FRMR attestation generator"](https://github.com/efterlev/efterlev/blob/main/DECISIONS.md) for the full schema-posture call.
