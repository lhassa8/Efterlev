# Threat Model

Efterlev is a compliance tool that reads source code, infrastructure-as-code, and configuration files. That material may contain secrets, private network topologies, and sensitive architecture information. A compliance tool that mishandles this material is worse than no tool at all.

This document names the threats Efterlev considers, the commitments Efterlev makes, and the risks users should be aware of.

---

## Trust boundaries

Efterlev operates across three trust boundaries:

1. **User's local environment ↔ Efterlev** — the user runs Efterlev locally against their own source. Full trust; Efterlev is executing on the user's machine.
2. **Efterlev ↔ LLM provider (Anthropic API)** — content Efterlev sends to the LLM provider leaves the user's machine. This is the only external network call Efterlev makes in normal operation.
3. **Efterlev ↔ downstream consumers of generated output** — generated artifacts (FRMR JSON, HTML, Markdown; OSCAL added in v1) are stored locally and shared by the user through their own channels. Efterlev does not publish or transmit these.

---

## Commitments

### No telemetry, no phone-home

Efterlev does not collect usage analytics, crash reports, or any other telemetry. It does not ping a central server on startup, shutdown, or during operation. There is no anonymous metrics collection.

The only outbound network calls Efterlev makes are:
- Anthropic API calls for LLM inference (configurable endpoint)
- Optional, explicit fetches of vendored catalog content (FRMR from `FedRAMP/docs`, NIST 800-53 from `usnistgov/oscal-content`) when the user runs `efterlev catalog update` — a v1 command; v0 ships a pinned set

No other network calls. Period.

### Local-only storage by default

All Efterlev state lives under `.efterlev/` in the user's working directory:
- `.efterlev/store/` — content-addressed blob store for evidence and claims
- `.efterlev/db.sqlite` — provenance graph and metadata
- `.efterlev/cache/` — cached catalog content (FRMR, NIST 800-53) and schema

These directories are user-readable only (permissions 0700 / 0600). They are gitignored by default in the initialized working directory.

### Secrets handling

Efterlev may encounter secrets during scanning — in Terraform variables, environment files, CI configurations, and source code. Commitments:

- **Secrets are never logged in plaintext.** If a detector encounters a value that pattern-matches a secret (AWS keys, API tokens, private keys, high-entropy strings adjacent to secret-ish identifiers), the value is hashed (SHA-256) before any logging, storage, or LLM transmission.
- **Secrets are never sent to the LLM.** The Documentation, Gap, and Remediation agents see redacted evidence records. Raw secret values never leave the local machine.
- **Secrets are flagged as findings.** Detected secrets produce a separate finding class (`secret_exposure`) that the user sees, with enough context to locate and rotate the secret without the secret itself being in the output.

Limitation: secret detection is pattern-based. A secret that doesn't match known patterns may pass through. Users should not rely on Efterlev as a secret scanner; tools like `trufflehog`, `gitleaks`, or cloud-provider secret managers are the right primary defense.

### LLM request minimization

Efterlev sends the minimum content necessary to the LLM provider for each generative task:

- Evidence records sent to the LLM are redacted (secrets hashed, identifiers tokenized where feasible)
- Agent system prompts are versioned and auditable in the repo (`agents/*_prompt.md`)
- Every LLM call is logged to the local provenance store with the prompt hash, model name, and timestamp — users can audit what left their machine

The LLM provider's data retention policy applies to these requests. Users concerned about this can configure a zero-data-retention endpoint (Anthropic offers this for API customers) or, in v1+, swap to a local model via the pluggable LLM backend.

### No automatic code modification

Efterlev generates remediation diffs as local output. It does not apply diffs, commit changes, or push to remote repositories in the hackathon MVP. The user reviews the diff and applies it manually (or not).

In v1+, an optional `--apply` flag may be added to the Remediation Agent for users who want automated local application. Opening PRs against remote repositories will remain explicit and opt-in.

### Dependency discipline

Efterlev pins its dependencies, scans them for known vulnerabilities as part of CI, and updates them on a regular cadence. The dependency list is kept small. New dependencies require justification in `DECISIONS.md`.

---

## Threats and mitigations

### T1: Sensitive source content exposed via LLM API

**Threat:** Terraform files, CI configs, or source code sent to the LLM provider contain sensitive information (secrets, internal architecture, customer data).

**Mitigations:**
- Secrets redacted before transmission (see above)
- Evidence records are scoped summaries, not raw source dumps — the LLM sees "this S3 bucket has encryption=aes256" not the entire `main.tf`
- User can configure zero-data-retention endpoints
- User can opt out of generative agents entirely and use only deterministic scanners

**Residual risk:** A sufficiently determined attacker with access to LLM provider logs could infer architectural details from redacted evidence records. Users who cannot accept this should run in scanner-only mode or use a local model (v1+).

### T2: Compromised detector

**Threat:** A malicious detector (from a third-party plugin package) reads source content and exfiltrates it.

**Mitigations:**
- Core Efterlev detectors are reviewed in the main repo; external detectors are opt-in.
- Detectors run in the Efterlev process but have no network access capability exposed through the detector API — if a detector wants to make a network call, it has to import the network stack directly, which is visible in code review.
- `efterlev detectors list` shows all loaded detectors, including third-party, before any scan runs.

**Residual risk:** A user who installs a malicious third-party detector package is trusting that package. This is the same trust model as any other Python package dependency.

### T3: Hallucinated evidence accepted as real

**Threat:** An LLM-generated narrative cites evidence that doesn't actually exist, or a mapping claims a control is evidenced when the underlying detector output doesn't support it.

**Mitigations:**
- Claims cannot be generated without linking to `evidence_ids` that must resolve in the provenance store
- The `validate_claim_provenance` primitive verifies every cited evidence_id exists before a claim is stored
- Rendered output always distinguishes Evidence (scanner-derived) from Claim (LLM-derived)
- Every claim carries a "DRAFT — requires human review" marker

**Residual risk:** An LLM could cite real evidence IDs but characterize them inaccurately in the narrative. Human review is the final defense; the tool does not claim to be a substitute for human review.

### T4: Provenance store tampering

**Threat:** A user or attacker modifies the local provenance store to fabricate evidence trails.

**Mitigations:**
- Content-addressed storage (SHA-256 of canonical content) — any modification to a stored record changes its ID and breaks downstream chains
- The provenance DB stores record hashes; `efterlev provenance verify` detects mismatches
- Users who need cryptographic non-repudiation can layer their own signing on top of the hashed records

**Non-mitigation:** Efterlev does not cryptographically sign its own output. If an auditor needs signed evidence, that's the user's responsibility (e.g., via Git commit signing, cosign, or a separate notarization step).

### T5: Supply chain compromise of Efterlev itself

**Threat:** A compromised Efterlev release transmits scanned content to an attacker.

**Mitigations:**
- Releases are signed (sigstore / cosign, to be established before v1 release)
- SBOMs are published per release
- The codebase is open source and auditable
- The dependency list is small and justified

**Residual risk:** Standard supply-chain risk for any open-source tool. Users can verify signatures on releases.

---

### T6: MCP attack surface

**Threat:** Efterlev exposes every primitive/agent to any process that can speak MCP over its stdio pipe. A malicious MCP client could drive Efterlev to scan arbitrary paths, burn API credits on LLM calls, or cite fabricated evidence in drafted output.

**Mitigations (per DECISIONS 2026-04-21 design call #4):**
- **Local-only transport.** The v0 server speaks MCP over stdio, never TCP. The caller must be able to spawn the `efterlev mcp serve` subprocess, which already implies local-shell access to the repo — the network attack surface is zero.
- **Subprocess-parent trust boundary.** The trust boundary is the OS-level stdio pipe. Whoever spawned the server is authorized to call every tool. This is the same trust model as `git`, `terraform`, and every other developer CLI.
- **Tool-call audit log.** Every MCP tool invocation writes one `ProvenanceRecord(record_type="claim", metadata={"kind": "mcp_tool_call", ...})` into the target repo's provenance store *before* dispatching the actual work. A user investigating a classification can see whether it came from their own CLI run or an external MCP caller (and which one — the MCP `clientInfo.name` is captured when available).
- **Evidence/source-file fencing survives the MCP boundary.** Agent tools run the same XML-fenced prompt path as the CLI (design call #3), so a hostile MCP caller cannot bypass prompt-injection defenses by injecting evidence through the MCP layer.
- **API keys stay server-side.** The Anthropic API key is read from the server process's environment, never passed in via MCP tool arguments. A client that can call `efterlev_agent_gap` can spend the server's API budget but cannot exfiltrate the key.

**Residual risk:**
- A client that can spawn the server has shell-equivalent access to the host and can do far worse than drive MCP tools. The MCP layer doesn't reduce that risk but doesn't amplify it either.
- Per-tool ACLs are a v1 concern. Users who want fine-grained control run the server only while they want external access.

**Not in scope for v0:**
- TCP transport with bearer tokens (see DECISIONS).
- Per-tool permission scopes (all-or-nothing at v0).
- Rate limiting on agent tools (a client can drive N LLM calls; operational cost is the user's to bound).

---

## Explicitly NOT in scope for the tool's threat model

- **Protecting the user from themselves.** Efterlev trusts its invoking user. A user who deliberately points Efterlev at sensitive content and chooses to use generative agents is making an informed decision.
- **Protecting against a compromised local environment.** If the user's machine is compromised, Efterlev's state is compromised with it. Efterlev is not designed as a security boundary against local adversaries.
- **Defending against regulatory-grade adversaries.** This is a compliance *drafting* tool. Systems needing nation-state-grade auditability should use tooling designed for that purpose.

---

## How to report a security issue

Security issues should be reported privately before public disclosure. See `SECURITY.md` in the repo for the disclosure process (to be added before v1 release).

We aim to acknowledge security reports within 48 hours and to publish a coordinated advisory on resolution.

---

## Review cadence

This threat model is reviewed:
- Before every minor release (v0.x → v0.y)
- After any architectural change affecting the trust boundaries above
- On receipt of a security report that reveals an unconsidered threat

The review log is kept in `DECISIONS.md` under the `[threat-model]` tag.
