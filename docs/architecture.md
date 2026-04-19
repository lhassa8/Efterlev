# Architecture

Efterlev is a repo-native compliance scanner for FedRAMP 20x and DoD Impact Levels. Its architectural bet is that compliance — traditionally a dashboard, a SaaS workflow, or a consulting engagement — is better served as a developer tool that lives in the codebase and produces auditable, provenance-tracked output. The whole system is organized around three load-bearing decisions: a strict evidence-versus-claims distinction in the data model, a provenance graph that every generated artifact roots back through, and a small stable primitive surface exposed via MCP so agents (ours and yours) can reason over it.

This document is the architectural overview. It does not re-state the full build plan (see [`docs/dual_horizon_plan.md`](./dual_horizon_plan.md)) or the user profile (see [`docs/icp.md`](./icp.md)). It is the briefing you read after the README and before the code.

## The three concepts

The codebase has three first-class abstractions, each with a different contract, a different rate of change, and different contribution ergonomics.

**Detectors** read source material (Terraform files, CI configs, application source) and emit `Evidence` records. They are rule-like and deterministic: given the same input, a detector produces the same evidence every time. Each detector lives as a self-contained folder at `src/efterlev/detectors/<cloud>/<capability>/` with five files — `detector.py`, `mapping.yaml`, `evidence.yaml`, `fixtures/`, and `README.md`. A contributor can add a new detector without reading or touching the rest of the codebase, which is the #1 design commitment for long-term project health. Detector IDs are capability-shaped (`encryption_s3_at_rest`) rather than control-numbered (`sc_28_s3_encryption`) because KSIs think in capabilities and capability-shaped IDs age better as the KSI ↔ 800-53 mapping evolves. See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the full detector contract.

**Primitives** are typed Python functions that represent agent-legible capabilities — `scan_terraform`, `load_frmr`, `map_ksi_to_controls`, `generate_attestation`, `validate_frmr`. There will be on the order of 15–25 primitives at v1. Every primitive is exposed via the MCP server the moment it exists; external agents can discover and call every one. A primitive's contract is two Pydantic models (one input, one output), a docstring naming side-effects and determinism, and a decorator that handles registration plus provenance emission. Primitives are the stable surface; they change deliberately and infrequently.

**Agents** are Claude-backed reasoning loops that compose primitives to produce a typed artifact — `GapReport`, `AttestationDraft`, `RemediationProposal`. Each agent has its system prompt in a sibling `.md` file (prompts are product code, not inline strings), consumes primitives through the MCP tool interface by default, and logs every tool call and model response to the provenance store. v0 ships three: Gap (classifies KSI status), Documentation (drafts FRMR attestations), Remediation (proposes code diffs).

The separation is deliberate. Detectors churn freely — the library grows with every contributed PR, and the internal shape of one detector has zero blast radius on the rest. Primitives are the stable shell around that churn. Agents are the product's brain; their prompts deserve human review even when code doesn't.

## Evidence versus Claims

Two distinct classes of information flow through Efterlev, treated differently throughout.

`Evidence` is deterministic, scanner-derived, and high-trust. Every evidence record carries a source reference (file path, line range, commit hash) plus the detector ID and version that produced it, the KSIs and 800-53 controls it evidences, and a content payload shaped by the detector's schema. Evidence is verifiable: anyone can look at the cited source line and confirm the detector's finding.

`Claim` is LLM-reasoned output — narrative, mapping proposal, remediation diff, KSI-status classification. Every claim carries a confidence level, a forced "DRAFT — requires human review" marker, an explicit `derived_from` list pointing to the evidence IDs (and/or other claim IDs) the claim is grounded in, the model name that produced it, and a hash of the system prompt used. A claim with no `derived_from` is structurally impossible; the `validate_claim_provenance` primitive rejects anything else.

The distinction shows up everywhere: in the data model, in rendered HTML, in FRMR output, in terminal summaries. An auditor reading any Efterlev artifact can always tell which layer they are looking at. This is the structural answer to "how do you defend against hallucination?" — not a disclaimer, but a type distinction the whole system is built around.

## Provenance

Every record — evidence, claim, finding, mapping, remediation — is a node in a directed graph stored locally. Edges point from derived records to their upstream sources. The graph is **content-addressed** (each record's ID is a SHA-256 of its canonical content), **append-only** (new evidence does not overwrite old evidence — it produces a new record, preserving history), and **versioned** (every primitive and detector carries a version, and those versions are captured in the records they emit).

Storage is SQLite for the graph structure and metadata, plus a content-addressed blob store on disk under `.efterlev/store/` for claim payloads. Portable, air-gap-friendly, local only by default.

The demo moment that this enables: `efterlev provenance show <claim_id>` walks the chain from a generated sentence in an FRMR attestation, through the reasoning step that produced it, through the evidence records cited, to the Terraform file and line the evidence came from. If the chain doesn't resolve cleanly, the claim is weak. v1's drift story is the same mechanic played forward in time: new scans produce new evidence records, and the append-only shape makes "what evidence for KSI-X changed in the last 30 days?" a structural query, not a bolt-on feature.

## FRMR and 800-53

Efterlev's user-facing surface speaks Key Security Indicators (KSIs) — the outcome-based, measurable units FedRAMP 20x built the Phase 1 and Phase 2 pilots around. Underneath, 800-53 Rev 5 remains the control catalog KSIs reference.

A detector declares both:

```python
@detector(
    id="aws.encryption_s3_at_rest",
    ksis=["KSI-SVC-VRI"],
    controls=["SC-28", "SC-28(1)"],
    source="terraform",
    version="0.1.0",
)
```

Its evidence records carry `ksis_evidenced` and `controls_evidenced` in parallel. Gap reports, attestation drafts, and HTML outputs all show the KSI as the primary organizing surface with the underlying controls shown alongside — because that is the distinction a user actually needs to see. An auditor wants to know both "is this KSI evidenced" and "which underlying 800-53 control has a mapped artifact." The data model answers both.

Two catalogs are vendored and loaded at startup:

- **FRMR** (`catalogs/frmr/FRMR.documentation.json`) from `FedRAMP/docs` — 11 KSI themes, 60 indicators, plus the FRR (FedRAMP Requirements and Recommendations) and FRD (Definitions) sections. Loaded with Pydantic directly; validated against the vendored `FedRAMP.schema.json`.
- **NIST SP 800-53 Rev 5** (`catalogs/nist/`) from `usnistgov/oscal-content` — the full 20-family catalog with enhancements. Loaded via `compliance-trestle`.

Both translate immediately into our internal Pydantic model. FRMR and OSCAL are output formats; the internal model is neither. See [`catalogs/README.md`](../catalogs/README.md) for the full provenance of each vendored file.

## OSCAL's role

OSCAL is a v1 secondary output format, not the internal representation and not the primary output. It exists in the architecture for three reasons: there is still a Rev5 transition cohort that submits OSCAL today; FedRAMP's RFC-0024 machine-readable compliance floor in September 2026 affects these users; and RegScale's OSCAL Hub (donated to the OSCAL Foundation in late 2025) is a real downstream consumer of what we produce. The v1 OSCAL generators will serialize `AttestationDraft`, `Evidence`, and `Claim` records into OSCAL Assessment Results, partial SSP, and POA&M artifacts validated against NIST's schemas.

At v0, OSCAL is input-only: we load the 800-53 catalog via trestle. Nothing in v0 emits OSCAL; nothing in the internal model is OSCAL-shaped. Adding OSCAL generators in v1 is additive — one more generator primitive per artifact type — not a rearchitecture. The decision record for why FRMR, not OSCAL, is the primary v0 output lives in [`DECISIONS.md`](../DECISIONS.md) under the 2026-04-19 entry.

## MCP as the agent interface

The MCP server in `src/efterlev/mcp_server/` exposes every primitive over stdio, with tool schemas generated from the primitives' Pydantic I/O models. The decorator that registers a primitive inside Efterlev's own process is the same decorator that publishes it to MCP.

This makes two things true. First, our own agents consume primitives through an interface that's identical to the one third-party agents get; if it works for our Gap Agent, it works for your Claude Code session. Second, you don't need to fork Efterlev to build a compliance workflow we don't ship. Point an MCP client at `efterlev mcp serve`, read the tool list, and you're using the same stable contract our agents use. The extension story isn't "learn Efterlev's internals" — it's "use the MCP surface."

## Where to go next

- [`docs/dual_horizon_plan.md`](./dual_horizon_plan.md) — what ships when; the 4-day hackathon plan and the post-hackathon roadmap
- [`docs/scope.md`](./scope.md) — the crisp v0 MVP contract, in and out of scope
- [`docs/icp.md`](./icp.md) — who this is for and how that shapes the product
- [`COMPETITIVE_LANDSCAPE.md`](../COMPETITIVE_LANDSCAPE.md) — honest positioning against Comp AI, RegScale OSCAL Hub, and others
- [`THREAT_MODEL.md`](../THREAT_MODEL.md) — the tool's own security posture
- [`DECISIONS.md`](../DECISIONS.md) — append-only record of non-trivial choices made while building this
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — the detector and primitive contracts, in contributor-facing form
