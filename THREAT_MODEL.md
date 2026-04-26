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

**Implemented (2026-04-23):** Every evidence body and source-file body
that flows into an LLM prompt is passed through a pattern-based
redaction pass before transmission. Matches are replaced with
structural `[REDACTED:<kind>:sha256:<8hex>]` tokens that preserve the
shape of the field (the model can still reason about "this value is
an AWS access key") without the secret itself. The helper lives at
`src/efterlev/llm/scrubber.py` and is called unconditionally from
`format_evidence_for_prompt` and `format_source_files_for_prompt` in
`src/efterlev/agents/base.py`. Fail-closed: a scrubber exception
propagates and prevents prompt transmission.

**Patterns covered (high-confidence, structural):**
- AWS access key IDs (`AKIA…`/`ASIA…`, IAM or STS)
- GCP API keys (`AIza…`)
- GitHub tokens (`gh[posur]_…`)
- Slack tokens (`xox[bpas]-…`)
- Stripe secret keys (`sk_(live|test)_…`)
- PEM-formatted private keys (RSA/DSA/EC/OPENSSH/PGP/generic)
- JWT-shaped base64url three-segment tokens

Each pattern has provenance documented in `scrubber.py` (where the
regex came from, what it catches, what it doesn't). The library is
deliberately small: high-confidence matches with very low false-
positive rates on legitimate infrastructure references (ARNs, resource
names, KMS key paths, region codes).

**Audit trail:** a `RedactionLedger` can be threaded through
`format_*_for_prompt` callers to capture every match with
`{timestamp, pattern_name, sha256_prefix, context_hint}`. The
`context_hint` names which evidence field or source file held the
match (e.g. `evidence[aws.iam_user_access_keys]:0`,
`source_file[iam.tf]`) but NEVER the secret value. The 8-hex-char
sha256 prefix provides enough entropy to distinguish redactions
within a scan but not enough to enable preimage recovery. Writing the
ledger to `.efterlev/redacted.log` (0600 perms) at end-of-scan is a
follow-up commit — the security property (no secrets in prompts)
does not depend on the log; the log is audit sugar.

**Limitations (not covered by the current pass):**
- **High-entropy strings adjacent to secret-ish keys.** Context-aware
  detection (detect `password|secret|token|key|cred` adjacent to a
  base64-shaped value) is harder to do without false-positives and is
  deferred. If your Terraform embeds generic API secrets without known
  prefixes, this pass will not catch them.
- **Custom or proprietary token formats.** Only the structural families
  listed above. A custom JWT-like or UUID-like token issued by your
  platform isn't in the library.
- **Secret-scanning is not our primary job.** Users who need exhaustive
  secret detection should run `trufflehog`, `gitleaks`, or equivalent
  upstream of Efterlev as the primary defense. Our scrubber is
  defense-in-depth for what reaches the LLM prompt.

**What a user can do today:**
- Run with the defaults — scrubbing is on and unconditional.
- Thread a `RedactionLedger` into agent calls for audit.
- Scanner-only mode: run `efterlev scan` and skip every `agent *`
  command. No LLM transmission at all — fullest protection.
- Zero-data-retention endpoint: Anthropic offers this for API customers.
- Pluggable LLM backend (v1 roadmap): swap to a local model when the
  Bedrock backend lands and a local-model backend lands after that.

### LLM request minimization

Efterlev sends the minimum content necessary to the LLM provider for each generative task:

- Agent system prompts are versioned and auditable in the repo (`agents/*_prompt.md`)
- Every LLM call is logged to the local provenance store with the prompt hash, model name, and timestamp — users can audit what left their machine
- Evidence is wrapped in per-run nonced XML fences (`<evidence_NONCE id="sha256:...">...</evidence_NONCE>`, post-review fixup F, 2026-04-22) and every agent runs a post-generation citation validator (`gap.py`, `documentation.py`, `remediation.py` each call `_validate_cited_ids`) that raises `AgentError` if the model cited a sha256 that did not appear in a legitimate fence in the prompt

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
- **Secret redaction before transmission (2026-04-23):** evidence content and source-file content are passed through `scrub_llm_prompt` inside `format_evidence_for_prompt` and `format_source_files_for_prompt`. Structural secrets (AWS access keys, GitHub/Slack/Stripe tokens, PEM private keys, JWTs, GCP API keys) are replaced with `[REDACTED:<kind>:sha256:<8hex>]` tokens before the prompt is assembled. Fail-closed on scrubber error. See the "Secrets handling" section above for the full pattern library.
- Evidence records are scoped structural summaries rather than raw source dumps — detectors emit facts like `{"encryption_state": "absent", "resource_name": "reports"}` not the full `main.tf` byte stream. Each detector's `evidence.yaml` documents the shape it emits; review it before running an agent in security-sensitive environments.
- User can configure zero-data-retention endpoints (Anthropic offers this for API customers)
- User can opt out of generative agents entirely and use only deterministic scanners (`efterlev scan` only; skip every `agent *` command)
- Every LLM call is content-addressed in the local provenance store; `efterlev provenance show` surfaces exactly what left the machine

**Residual risk:** Pattern-based detection is not exhaustive. Custom token formats, high-entropy strings adjacent to secret-ish keys without known prefixes, and generic API secrets without structural markers are NOT caught by the current pass. Defense-in-depth requires running `trufflehog` / `gitleaks` upstream as the primary secret-scanning defense. For maximum protection on secret-laden repos, use scanner-only mode.

### T2: Compromised detector

**Threat:** A malicious detector (from a third-party plugin package) reads source content and exfiltrates it.

**Mitigations:**
- Core Efterlev detectors are reviewed in the main repo; external detectors are opt-in.
- Detectors run in the Efterlev process but have no network access capability exposed through the detector API — if a detector wants to make a network call, it has to import the network stack directly, which is visible in code review.
- `efterlev detectors list` shows all loaded detectors, including third-party, before any scan runs.

**Residual risk:** A user who installs a malicious third-party detector package is trusting that package. This is the same trust model as any other Python package dependency.

### T3: Hallucinated evidence accepted as real

**Threat:** An LLM-generated narrative cites an `evidence_id` that the model fabricated, or characterizes real evidence inaccurately.

**Mitigations implemented at v0:**
- Claims' `derived_from` structure requires explicit citation of `evidence_id`s the model saw in the prompt.
- **Per-run nonced XML fences** (`agents/base.py:new_fence_nonce` + `format_evidence_for_prompt`) wrap every evidence record with a 32-bit hex nonce the model cannot guess. Content inside a fence cannot forge a matching fence boundary.
- **Per-agent post-generation citation validators** (`gap._validate_cited_ids`, `documentation._validate_cited_ids`, `remediation._validate_citations`) parse the prompt's fenced regions and reject any Claim whose cited evidence IDs did not appear inside a legitimately-nonced fence. Rejection raises `AgentError` and prevents Claim storage. This enforces the "cite only what you actually saw" property at the agent boundary.
- **Store-level `_validate_claim_derived_from`** (`provenance/store.py`, 2026-04-23 design): defense-in-depth at the write boundary — every Claim's `derived_from` is verified to resolve as either a `ProvenanceRecord.record_id` OR an `Evidence.evidence_id` in a stored evidence payload (dual-key lookup) BEFORE the record is inserted. Catches the gap a buggy agent or direct-store-write path could create where the agent-level fence check doesn't run.
- **Empty-evidence-ids classification rejection** (2026-04-25 SPEC-57 round-2 response): `KsiClassification` Pydantic `model_validator` rejects `status="implemented"` or `status="partial"` with `evidence_ids=[]`. The fence validator catches IDs the model fabricated against prompt fences but doesn't fire on zero citations — different bug class, different defense layer.
- Rendered output always distinguishes Evidence (scanner-derived) from Claim (LLM-derived).
- Every claim carries a "DRAFT — requires human review" marker; `AttestationArtifact.provenance.requires_review` is a `Literal[True]` Pydantic invariant that cannot be downgraded without a type-level change.

**Residual risk:** An LLM could cite real evidence IDs but characterize them inaccurately in the narrative. Human review is the final defense; the tool does not claim to be a substitute for human review. SPEC-57.1's `evidence_layer_inapplicable` status (2026-04-25) helps reviewers prioritize by separating coverage gaps from compliance findings, but does not replace human judgment on narrative accuracy.

### T4: Provenance store tampering

**Threat:** A user or attacker modifies the local provenance store to fabricate evidence trails.

**Mitigations:**
- Content-addressed storage (SHA-256 of canonical content) — any modification to a stored record changes its ID and breaks downstream chains.
- The provenance DB stores record hashes; **`efterlev provenance verify` detects mismatches** by walking every record, recomputing each blob's SHA-256, and comparing to the hash embedded in the sharded `content_ref` path. Exit 0 = clean; exit 1 = mismatches listed by record_id (tampering, disk corruption, partial-write). Implemented 2026-04-25 in response to the round-2 review's finding that the command was claimed in the threat model but didn't exist.
- Users who need cryptographic non-repudiation can layer their own signing on top of the hashed records.

**Non-mitigation:** Efterlev does not cryptographically sign its own output. If an auditor needs signed evidence, that's the user's responsibility (e.g., via Git commit signing, cosign, or a separate notarization step).

### T5: Supply chain compromise of Efterlev itself

**Threat:** A compromised Efterlev release transmits scanned content to an attacker.

**Current state at v0 (honest):** the repo is private, the package is not yet published to PyPI (version 0.0.1 per `pyproject.toml`), and no release artifacts are signed. The "releases are signed" language previously in this section was aspirational. Users install via `uv sync --extra dev` against a cloned repo, not via a packaged release.

**Mitigations implemented today:**
- The codebase is pre-launch private, staged for a public Apache-2.0 flip once the eight pre-launch readiness gates pass (DECISIONS 2026-04-23 "Rescind closed-source lock"). Full code auditability is a launch deliverable.
- The dependency list is small and justified (every non-trivial dep has a DECISIONS entry).
- Vendored catalogs (`catalogs/frmr/`, `catalogs/nist/`) are SHA-256-pinned at load time — see `src/efterlev/paths.py::verify_catalog_hashes`. A tampered catalog fails `efterlev init`.

**Planned for public launch (pre-launch readiness gate A5, trust surface):**
- Sigstore / cosign signing of release artifacts (wheel, sdist, container images).
- SLSA provenance on each release artifact.
- Published SBOMs per release.
- Coordinated-disclosure channel via GitHub Security Advisories + `security@efterlev.com` mailbox.
- Dependabot/Renovate enabled on `main` once public.
- Pre-launch threat-model review with public-repo posture applied (attacker can read source, open PRs, influence vendored content).

**Residual risk at v0:** users running Efterlev out of a cloned repo must verify they trust the source. Git commit signing is the closest-available integrity mechanism pending sigstore.

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

### T7: Public-repo source review for prompt-injection paths (added 2026-04-25 per SPEC-30.2)

**Threat:** With the repo public, an attacker can read every agent prompt, the secret-redaction pattern library, and the provenance-store schema. They can then craft Terraform fixtures, Evidence Manifests, or cited evidence-id strings designed to slip past per-agent fence validators or the scrubber's pattern set.

**Mitigation:** Per-run-nonced XML fences make content-injected forged fences computationally infeasible to predict; the post-launch posture publishes the algorithm but the per-run nonce is generated at agent invocation. Secret redaction operates on structural patterns that cannot be enumerated faithfully without seeing the pattern library, but the patterns are conservative — over-redaction is the safe-failure mode. Reports of bypass paths flow through `SECURITY.md` (SPEC-30.1) and become test fixtures.

**Residual risk:** A determined attacker who can both author the Terraform input AND read the prompt structure may still find new bypass shapes; the project's response cadence matters more than the static defense in depth.

### T8: Malicious PR (backdoor in detector or agent prompt) (added 2026-04-25 per SPEC-30.2)

**Threat:** A contributor opens a PR that introduces a subtle backdoor — a detector that silently fails on a specific resource pattern, an agent prompt change that weakens citation discipline, or a dependency that pulls in malicious transitive code.

**Mitigation:** Branch protection on `main` (SPEC-04, `.github/BRANCH_PROTECTION.md`): every PR requires maintainer review; CODEOWNERS enforces gating; merge requires linear history; force-push is disallowed; signed commits required for maintainer-authored commits. CI security scans (SPEC-30.7) catch known-bad patterns. The maintainer reviews every PR's full diff during the BDFL era; a hostile contributor needs to bypass both human review and automated scanning.

**Residual risk:** Sophisticated supply-chain attacks targeting maintainer credentials or CI pipelines (e.g., the SolarWinds-style attack class). Sigstore + SLSA provenance on releases (SPEC-08) constrains the post-merge attack window; tamper-evident.

### T9: Dependency poisoning (added 2026-04-25 per SPEC-30.2)

**Threat:** A direct or transitive Python dependency is compromised between Efterlev releases. Malicious code reaches the user's machine via `pipx install efterlev`.

**Mitigation:** Pinned dependency versions in `pyproject.toml` with explicit upper bounds; Dependabot weekly updates flow as PRs the maintainer reviews (SPEC-30.6); `pip-audit` CI scan blocks PRs that introduce known vulnerable versions (SPEC-30.7). Container images bake dependencies in at build time, then sign the immutable artifact via Sigstore (SPEC-06 + SPEC-08).

**Residual risk:** Zero-day in a dep that lands between an audit pass and a release. Mitigated only by response cadence; documented in SECURITY.md as the coordinated-disclosure window.

### T10: Release-artifact tampering (added 2026-04-25 per SPEC-30.2)

**Threat:** An attacker swaps a Sigstore-signed wheel/container with a malicious one between release upload and user download.

**Mitigation:** Sigstore keyless-OIDC signatures bind the artifact to the GitHub Actions workflow that built it (SPEC-08); SLSA provenance attestations cryptographically link wheel/container → workflow → commit SHA → repo. The verification script `scripts/verify-release.sh` runs all three checks; the release-notes template documents how users self-verify.

**Residual risk:** A user who skips verification has no protection beyond TLS to PyPI / ghcr.io. The coordinated-disclosure-on-tamper process in SECURITY.md is the response path.

---

## What changes when the repo goes public (2026-04-25)

The trust posture shifts at the public-flip moment:

- **Before:** the codebase was readable only by the maintainer + invited reviewers under NDA; threat T7-style attacks required social-engineering to obtain access.
- **After:** the codebase is fully public; T7-T10 above are explicitly in-scope.

The mitigations under T7-T10 were designed before the open-source-first commitment was locked (DECISIONS 2026-04-23) and are validated by SPEC-30.7's CI security scanning + SPEC-30.8's pre-launch security review.

The post-flip threat model is reviewed every minor release per the cadence below, and after any architectural change affecting the trust boundaries.

---

## Explicitly NOT in scope for the tool's threat model

- **Protecting the user from themselves.** Efterlev trusts its invoking user. A user who deliberately points Efterlev at sensitive content and chooses to use generative agents is making an informed decision.
- **Protecting against a compromised local environment.** If the user's machine is compromised, Efterlev's state is compromised with it. Efterlev is not designed as a security boundary against local adversaries.
- **Defending against regulatory-grade adversaries.** This is a compliance *drafting* tool. Systems needing nation-state-grade auditability should use tooling designed for that purpose.

---

## How to report a security issue

Security issues should be reported privately before public disclosure. See [`SECURITY.md`](./SECURITY.md) for the full coordinated-disclosure process: GitHub Security Advisories at [github.com/efterlev/efterlev/security/advisories/new](https://github.com/efterlev/efterlev/security/advisories/new) (preferred) or `security@efterlev.com` (alternate). Acknowledgment within 3 business days; 90-day default coordinated-disclosure window.

---

## Review cadence

This threat model is reviewed:
- Before every minor release (v0.x → v0.y)
- After any architectural change affecting the trust boundaries above
- On receipt of a security report that reveals an unconsidered threat

The review log is kept in `DECISIONS.md` under the `[threat-model]` tag.
