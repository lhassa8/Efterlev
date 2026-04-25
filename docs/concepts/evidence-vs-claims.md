# Evidence vs Claims

> Why Efterlev distinguishes scanner output from LLM output, and why a 3PAO cares.

This page is a placeholder for SPEC-38.4. Substantial content lands in a follow-up batch.

The short version: every artifact Efterlev produces falls into one of two classes.

- **Evidence** is deterministic, scanner-derived, high-trust. Produced by detectors. Carries a content-addressed ID and a source reference (file + line + hash). Same input always produces the same output.
- **Claims** are reasoned output — LLM-generated narratives, mappings, classifications, remediation proposals. Carry a confidence indicator and an explicit `DRAFT — requires human review` marker. The marker is enforced at the type level (`Literal[True]`), not configurable.

The distinction is visible everywhere: the data model, the HTML reports (Evidence cards are green-bordered; Claim cards are amber with the DRAFT banner), the FRMR attestation JSON, the provenance store. This is the defensible answer to "how does a 3PAO trust this?" — they don't trust the claims; they trust the evidence, and the claims are drafts that accelerate the human review.

[Read the full architecture →](../architecture.md)
