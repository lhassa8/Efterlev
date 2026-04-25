# Architecture

Efterlev is a repo-native compliance scanner for FedRAMP 20x and DoD Impact Levels. Its architectural bet is that compliance — traditionally a dashboard, a SaaS workflow, or a consulting engagement — is better served as a developer tool that lives in the codebase and produces auditable, provenance-tracked output. The whole system is organized around three load-bearing decisions: a strict evidence-versus-claims distinction in the data model, a provenance graph that every generated artifact roots back through, and a small stable primitive surface exposed via MCP so agents (ours and yours) can reason over it.

This document is the architectural overview. It does not re-state the full build plan (see [`docs/dual_horizon_plan.md`](./dual_horizon_plan.md)) or the user profile (see [`docs/icp.md`](./icp.md)). It is the briefing you read after the README and before the code.

## The three concepts

The codebase has three first-class abstractions, each with a different contract, a different rate of change, and different contribution ergonomics.

**Detectors** read source material (Terraform files, CI configs, application source) and emit `Evidence` records. They are rule-like and deterministic: given the same input, a detector produces the same evidence every time. Each detector lives as a self-contained folder at `src/efterlev/detectors/<cloud>/<capability>/` with five files — `detector.py`, `mapping.yaml`, `evidence.yaml`, `fixtures/`, and `README.md`. A contributor can add a new detector without reading or touching the rest of the codebase, which is the #1 design commitment for long-term project health. Detector IDs are capability-shaped (`encryption_s3_at_rest`) rather than control-numbered (`sc_28_s3_encryption`) because KSIs think in capabilities and capability-shaped IDs age better as the KSI ↔ 800-53 mapping evolves. See [`CONTRIBUTING.md`](https://github.com/efterlev/efterlev/blob/main/CONTRIBUTING.md) for the full detector contract.

**Primitives** are typed Python functions that represent agent-legible capabilities — `scan_terraform`, `load_frmr`, `map_ksi_to_controls`, `generate_attestation`, `validate_frmr`. There will be on the order of 15–25 primitives at v1. Every primitive is exposed via the MCP server the moment it exists; external agents can discover and call every one. A primitive's contract is two Pydantic models (one input, one output), a docstring naming side-effects and determinism, and a decorator that handles registration plus provenance emission. Primitives are the stable surface; they change deliberately and infrequently.

**Agents** are Claude-backed reasoning loops that compose primitives to produce a typed artifact — `GapReport`, `AttestationDraft`, `RemediationProposal`. Each agent has its system prompt in a sibling `.md` file (prompts are product code, not inline strings), consumes primitives through the MCP tool interface by default, and logs every tool call and model response to the provenance store. v0 ships three: Gap (classifies KSI status), Documentation (drafts FRMR attestations), Remediation (proposes code diffs).

The separation is deliberate. Detectors churn freely — the library grows with every contributed PR, and the internal shape of one detector has zero blast radius on the rest. Primitives are the stable shell around that churn. Agents are the product's brain; their prompts deserve human review even when code doesn't.

## Evidence versus Claims

Two distinct classes of information flow through Efterlev, treated differently throughout.

`Evidence` is deterministic, scanner-derived OR human-attested, and high-trust. Every evidence record carries a source reference (file path, line range, commit hash) plus the detector ID (or `"manifest"` for human-signed attestations) and version, the KSIs and 800-53 controls it evidences, and a content payload shaped by the detector's schema. Evidence is verifiable: anyone can look at the cited source line — `.tf` for scanner-derived, `.efterlev/manifests/*.yml` for human-attested — and confirm the record's content.

**Two Evidence sources (v1):** detector Evidence is produced by a `@detector` reading typed source material (Terraform today; CloudFormation / K8s / runtime in v1.5+). Manifest Evidence is produced by the `load_evidence_manifests` primitive reading customer-authored YAML attestations under `.efterlev/manifests/`. Both land as the same `Evidence` Pydantic type in the provenance store; the `detector_id` field distinguishes them (`"aws.encryption_s3_at_rest"` vs `"manifest"`). Renderers visually separate them with an "attestation" badge on manifest-sourced citations. The Gap Agent's prompt sees both through the same XML fences and treats both as untrusted data to reason about; the fence-citation validator is the same.

`Claim` is LLM-reasoned output — narrative, mapping proposal, remediation diff, KSI-status classification. Every claim carries a confidence level, a forced "DRAFT — requires human review" marker, an explicit `derived_from` list pointing to the evidence IDs (and/or other claim IDs) the claim is grounded in, the model name that produced it, and a hash of the system prompt used. A claim with no `derived_from` is structurally impossible; the post-generation fence-citation validators in each agent reject fabricated IDs.

The distinction shows up everywhere: in the data model, in rendered HTML, in FRMR output, in terminal summaries. An auditor reading any Efterlev artifact can always tell which layer they are looking at. This is the structural answer to "how do you defend against hallucination?" — not a disclaimer, but a type distinction the whole system is built around.

### Prompt-injection defense: nonced XML fences

Evidence content (detector output, manifest statements, Terraform comments) is attacker-controllable at the input boundary. Naive string embedding would let a hostile manifest or `.tf` comment break out of its fence and inject fake evidence IDs that pass the citation validator. Efterlev's defense (2026-04-22 post-review fixup F): every agent `run()` generates a fresh random hex nonce via `secrets.token_hex(4)`. Fences become `<evidence_NONCE id="sha256:..."> ... </evidence_NONCE>` (and `<source_file_NONCE path="...">` for Terraform source). The post-generation parser accepts only fences whose nonce matches the caller's; content-injected fences with any other nonce are ignored. An adversarial content author would need to predict 32 bits of entropy at authoring time to forge a fence — infeasible.

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
    ksis=[],  # DECISIONS 2026-04-21 design call #1: SC-28 has no FRMR KSI
    controls=["SC-28", "SC-28(1)"],
    source="terraform",
    version="0.1.0",
)
```

Its evidence records carry `ksis_evidenced` and `controls_evidenced` in parallel. Gap reports, attestation drafts, and HTML outputs all show the KSI as the primary organizing surface with the underlying controls shown alongside — because that is the distinction a user actually needs to see. An auditor wants to know both "is this KSI evidenced" and "which underlying 800-53 control has a mapped artifact." The data model answers both. When a control evidenced by a detector has no FRMR KSI mapping (SC-28 today), the Gap Agent surfaces those records in an explicit "Unmapped findings" section rather than shoehorning them into a thematically-adjacent KSI.

One subtlety on `ksis_evidenced`: per [DECISIONS 2026-04-21](https://github.com/efterlev/efterlev/blob/main/DECISIONS.md) — "Evidence.ksis_evidenced is default attribution, not authoritative" — the field represents the detector's *default* attribution, not the complete set of KSIs this evidence can inform. Agents may cite a given evidence record across additional KSIs through reasoning (e.g., a CloudTrail record attributed to KSI-MLA-LET also speaking to KSI-CMT-LMC's change-monitoring semantics). The Documentation Agent honors whatever evidence the Gap Agent cited; the fence-citation validator bounds this to "evidence the scanner actually produced."

Two catalogs are vendored and loaded at startup:

- **FRMR** (`catalogs/frmr/FRMR.documentation.json`) from `FedRAMP/docs` — 11 KSI themes, 60 indicators, plus the FRR (FedRAMP Requirements and Recommendations) and FRD (Definitions) sections. Loaded with Pydantic directly; validated against the vendored `FedRAMP.schema.json`.
- **NIST SP 800-53 Rev 5** (`catalogs/nist/`) from `usnistgov/oscal-content` — the full 20-family catalog with enhancements. Loaded via `compliance-trestle`.

Both translate immediately into our internal Pydantic model. FRMR and OSCAL are output formats; the internal model is neither. See [`catalogs/README.md`](https://github.com/efterlev/efterlev/blob/main/catalogs/README.md) for the full provenance of each vendored file.

## FRMR attestation output (v1 Phase 2, landed 2026-04-22)

The v1 primary production output is an `AttestationArtifact` — a typed Pydantic model serialized to canonical JSON. The `generate_frmr_attestation` primitive assembles it from a list of `AttestationDraft` records (produced by the Documentation Agent) plus the loaded FRMR indicator catalog. The artifact's structure mirrors FRMR's conventions (top-level `info` + `KSI` keyed by theme short_name + indicator records under each theme) but is NOT a valid FRMR *catalog* document — FedRAMP has not published an attestation-output schema as of April 2026, and our artifact carries attestation data (status, mode, narrative, citations, `claim_record_id`) the FRMR catalog schema rejects under `additionalProperties: false`.

Validation posture: Pydantic `extra="forbid"` and strict `Literal` types at construction time. A malformed artifact raises `ValidationError` before serialization. `AttestationArtifactProvenance.requires_review` is `Literal[True]` — a construction-time invariant that Pydantic enforces. No caller can construct an artifact claiming reviewer-final status; when the Phase 5 review workflow lands, `reviewed_by` and `approved_by` are additive trail fields that do not flip `requires_review`.

Canonical JSON: sorted keys, indent=2, UTF-8, newline-terminated — byte-stable across runs for a given input (with `generated_at` pinned), which supports the Phase 4 drift story (diff two scans' artifacts) and content-addressable audit trails.

The `efterlev agent document` CLI path emits both the existing HTML report and an `attestation-<ts>.json` artifact. Full design call in `DECISIONS.md` 2026-04-22 "Phase 2: FRMR attestation generator."

## OSCAL's role

OSCAL is **deferred to v1.5+** (not v1), gated on customer pull. The architecture continues to support it — the internal `AttestationDraft` / `Evidence` / `Claim` / `AttestationArtifact` records are generator-format-agnostic, and the `oscal/` package slot exists — but the SSP / Assessment Results / POA&M generators are not built at v1. Rev5-transition users and RegScale OSCAL-Hub-consuming prospects are the signal that pulls them forward. See `DECISIONS.md` 2026-04-22 "Lock v1 scope" for the sequencing call and `DECISIONS.md` 2026-04-22 "Phase 2: FRMR attestation generator" for the schema-posture rationale.

At v0 and v1, OSCAL is input-only: we load the 800-53 catalog via trestle. Nothing today emits OSCAL; nothing in the internal model is OSCAL-shaped. When the v1.5 OSCAL generators land they'll serialize the same internal records the FRMR generator serializes today — additive, not a rearchitecture.

## MCP as the agent interface

The MCP server in `src/efterlev/mcp_server/` exposes every primitive over stdio, with tool schemas generated from the primitives' Pydantic I/O models. The decorator that registers a primitive inside Efterlev's own process is the same decorator that publishes it to MCP.

This makes two things true. First, our own agents consume primitives through an interface that's identical to the one third-party agents get; if it works for our Gap Agent, it works for your Claude Code session. Second, you don't need to fork Efterlev to build a compliance workflow we don't ship. Point an MCP client at `efterlev mcp serve`, read the tool list, and you're using the same stable contract our agents use. The extension story isn't "learn Efterlev's internals" — it's "use the MCP surface."

## Where to go next

- [`docs/dual_horizon_plan.md`](./dual_horizon_plan.md) — what ships when; the 4-day hackathon plan and the post-hackathon roadmap
- [`docs/scope.md`](./scope.md) — the crisp v0 MVP contract, in and out of scope
- [`docs/icp.md`](./icp.md) — who this is for and how that shapes the product
- [`COMPETITIVE_LANDSCAPE.md`](https://github.com/efterlev/efterlev/blob/main/COMPETITIVE_LANDSCAPE.md) — honest positioning against Comp AI, RegScale OSCAL Hub, and others
- [`THREAT_MODEL.md`](https://github.com/efterlev/efterlev/blob/main/THREAT_MODEL.md) — the tool's own security posture
- [`DECISIONS.md`](https://github.com/efterlev/efterlev/blob/main/DECISIONS.md) — append-only record of non-trivial choices made while building this
- [`CONTRIBUTING.md`](https://github.com/efterlev/efterlev/blob/main/CONTRIBUTING.md) — the detector and primitive contracts, in contributor-facing form
