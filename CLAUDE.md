# CLAUDE.md — Efterlev

This file is your persistent context. Read it in full at the start of every session.

---

## What we're building

**Efterlev** is a repo-native, agent-first compliance scanner for FedRAMP 20x and DoD Impact Levels. It lives in the developer's codebase and CI pipeline — not in a dashboard — and it produces code-level findings, remediation diffs, and FRMR-compatible validation data (the machine-readable format FedRAMP 20x is standardizing on) for downstream consumption. OSCAL generation is a v1 secondary output format for users transitioning Rev5 submissions or feeding downstream tools like RegScale's OSCAL Hub.

Efterlev's primary internal abstraction is the **Key Security Indicator (KSI)** — the outcome-based, measurable unit FedRAMP 20x built the pilot around. Detectors evidence KSIs; KSIs map to 800-53 controls; 800-53 remains the underlying catalog. The user-facing surface speaks KSIs.

The name "Efterlev" is a shortening of the Swedish *efterlevnad* (compliance). Pronounce it "EF-ter-lev."

**Primary user (the ICP lens for every product decision):** a SaaS company (50–200 engineers) pursuing its first FedRAMP Moderate authorization, with a committed federal deal on the line. Full ICP at `docs/icp.md` — read it before proposing features, because the ICP is how we decide what Efterlev does and doesn't do.

The full plan lives in `docs/dual_horizon_plan.md`. **Read it before proposing any architectural change.** Competitive positioning lives in `COMPETITIVE_LANDSCAPE.md` — read that before making any positioning-adjacent claim.

We are building this as a pure-OSS Apache-2.0 project. It started as a 4-day hackathon demo, then extended into v1 development; the open-source-first launch posture was locked 2026-04-23 (see `DECISIONS.md` entry of that date). The architecture is designed so that nothing built in the hackathon layer or the closed-development window needs to be thrown away to build the v1 layer — every artifact the public repo ships at launch already exists.

---

## v1 scope locked 2026-04-22 (amended 2026-04-23)

Three commitments from the 2026-04-22 scope lock survive; the fourth (closed-source through v1) was rescinded 2026-04-23. See `DECISIONS.md` 2026-04-22 "Lock v1 scope" for the original entry and `DECISIONS.md` 2026-04-23 "Rescind closed-source lock" for the amendment. Key adjustments that affect day-to-day decisions:

- **Archetype-first.** No named design partner. ICP A per `docs/icp.md` is the lens; concrete schema choices (Evidence Manifest, Phase 6 detector priorities) may be revised when the first real user surfaces — more likely through public GitHub discovery post-launch than through private outreach.
- **Commercial AWS + GovCloud both first** *(amended 2026-04-23)*. AWS Bedrock backend — originally Phase 3 gated on prospect pull — is now pre-launch readiness gate A3. The "runs where the customer wants to run it" promise of the OSS launch is hollow without GovCloud support.
- **20x-native output first.** FRMR-attestation generator is the only v1 production output. OSCAL SSP/AR/POA&M generators move to v1.5+, gated on customer pull. The `oscal/` generator slot stays in the architecture but is empty.
- **~~Closed-source through v1~~** (rescinded 2026-04-23). Efterlev ships as a public Apache-2.0 repository when the eight pre-launch readiness gates pass (A1 identity through A8 launch rehearsal). Monetization posture: pure OSS, no commercial tier, no paid layer — ever. License stays Apache 2.0 throughout.

The non-negotiable principles below remain authoritative. Principle 3 (FRMR primary, OSCAL secondary) — unchanged in intent; OSCAL-as-secondary moves from v1 to v1.5+. Principle 4 (community-contributable detector library) — unpaused as of 2026-04-23; the public-launch flip is what activates external contribution flow, and all detector-contract scaffolding (CONTRIBUTING tutorial, `good first issue` ticket design) is pre-launch readiness work.

---

## What's shipped (as of 2026-04-22)

v0 is complete on `main`. v1 Phase 1 and Phase 2, plus six post-review fixups, have landed on `claude/review-github-access-6XZIA`:

**v0 (main, commit `6fb7e75`):**
- 6 AWS-Terraform detectors: `encryption_s3_at_rest`, `tls_on_lb_listeners`, `fips_ssl_policies_on_lb_listeners`, `mfa_required_on_iam_policies`, `cloudtrail_audit_logging`, `backup_retention_configured`. Phase 6-lite (see below) brings the total to 12.
- 3 agents: Gap, Documentation, Remediation. All use Opus 4.7 (Documentation on Sonnet 4.6). All three enforce XML-fenced evidence + post-generation citation validation.
- MCP stdio server exposing every primitive.
- Provenance graph: SQLite + content-addressed blob store + receipt log.
- HTML renderers for every agent output.
- FRMR + 800-53 catalogs vendored with pinned SHA-256 hashes.

**Phase 1 — Evidence Manifests (`d43a2a3`, `7cc86d6`):** Customers author `.efterlev/manifests/*.yml` with human-signed procedural attestations. `EvidenceManifest` Pydantic model, file loader, `load_evidence_manifests` primitive in the `evidence/` capability slot. Manifest attestations become `Evidence` records with `detector_id="manifest"` and flow through the Gap Agent alongside detector Evidence. Documentation Report's citations visually distinguish manifest-sourced from scanner-sourced with an amber "attestation" badge. Takes coverage from ~20% (scanner-only) toward 80%+ (scanner + procedural). Full design call: DECISIONS 2026-04-22 "Phase 1: Evidence Manifests."

**Phase 2 — FRMR attestation generator (`5d35bf7`):** `generate_frmr_attestation` primitive serializes `AttestationDraft` to FRMR-compatible JSON. Typed `AttestationArtifact` Pydantic model with `info` + `KSI`-by-theme + `provenance` blocks, `extra="forbid"` everywhere, `requires_review: Literal[True]` as a construction-time invariant. Canonical JSON output (sorted keys, indent=2). `efterlev agent document` now writes `attestation-<ts>.json` alongside the HTML report. The FRMR `catalogs/frmr/FedRAMP.schema.json` describes the catalog not the attestation output; FedRAMP has not published an attestation schema as of April 2026, so Pydantic structural validation is the v1 guarantee. Full design call: DECISIONS 2026-04-22 "Phase 2: FRMR attestation generator."

**Post-review fixups A–F (`e62e309` → `fcaf94a`):** A deep-dive review surfaced 14 findings; all resolved.
- A: small tightenings (specific `pydantic.ValidationError` catch, `skipped_unknown_ksi` dedup at primitive boundary, hard-error on missing FRMR cache in `scan`, consolidated ProvenanceStore in `agent document`, CLAUDE.md schema-posture refresh).
- B: `docs/dual_horizon_plan.md` §3.1 Layer 2 rewritten to reflect the v1 lock.
- C: Remediation Agent filters manifest Evidence out of source-file assembly; short-circuits cleanly on manifest-only KSIs.
- D: `Evidence.source_ref.file` is repo-relative, not absolute — no filesystem layout leaked into the FRMR JSON or HTML artifacts. `parse_terraform_file(path, record_as=...)` and `LoadEvidenceManifestsInput.scan_root` are the anchors.
- E: Gap Report + Remediation Report both carry the manifest "attestation" badge when passed `evidence=`; CSS consolidated in the shared stylesheet.
- F: Per-run fence nonce (`secrets.token_hex(4)`) prevents content-injected forged fences. `<evidence_NONCE id="...">` and `<source_file_NONCE path="...">`; parse helpers take the nonce and ignore any fence with a different one. Full design call: DECISIONS 2026-04-22 "Post-review fixups A–F."

**E2E smoke harness (`b3014e7`, `5913af7`):** `scripts/e2e_smoke.py` shells out to `uv run efterlev …` across init → scan → agent gap → agent document → agent remediate against an embedded Terraform fixture exercising every registered detector plus one KSI-AFR-FSI Evidence Manifest. Results land in `.e2e-results/<UTC-ISO-TS>/` with captured stdio, copied artifacts, `checks.json`, and `summary.md`. Checks split into critical (13, fail the run), quality (5, warn), and info (per-stage). Gated on `ANTHROPIC_API_KEY` — exits 2 if unset. Pytest wrapper at `tests/test_e2e_smoke.py` for `pytest -k e2e`. First real-Opus run: all five CLI stages exited 0, 60/60 classifications produced (no truncation at 16384 max_tokens), fence validator held, FRMR artifact parsed clean with no absolute-path leaks, manifest-KSI narrative grounded in the attestor's keywords. Full design call: DECISIONS 2026-04-22 "E2E smoke harness landed + first real-Opus run."

**Phase 6-lite — 6 additional detectors (batch on `phase-6-lite`):** Doubles the detector count from 6 to 12, moving toward the v1 target of 30. New detectors:
- `aws.s3_public_access_block` — AC-3, `ksis=[]` (no KSI in FRMR maps AC-3).
- `aws.rds_encryption_at_rest` — SC-28 / SC-28(1), `ksis=[]` (mirrors encryption_s3_at_rest).
- `aws.kms_key_rotation` — SC-12 / SC-12(2), `ksis=[]` (no KSI maps SC-12). Distinguishes symmetric CMKs (rotation applies) from asymmetric (rotation_status=not_applicable).
- `aws.cloudtrail_log_file_validation` — AU-9, `ksis=[KSI-MLA-OSM]` (FRMR lists au-9 in that KSI). Runs alongside the existing cloudtrail_audit_logging detector; different control family.
- `aws.vpc_flow_logs_enabled` — AU-2 / AU-12, `ksis=[KSI-MLA-LET]`. Records target_kind (vpc/subnet/eni), traffic_type, destination_type.
- `aws.iam_password_policy` — IA-5 / IA-5(1), `ksis=[]`. Does NOT claim KSI-IAM-MFA despite IA-5 appearing in that KSI's controls array — password policy does not evidence phishing-resistant MFA. Control membership is necessary but not sufficient for claiming a KSI.
4 of 6 declare `ksis=[]` per the SC-28 precedent (DECISIONS 2026-04-21 design call #1, Option C). Full design call: DECISIONS 2026-04-22 "Phase 6-lite: 6 additional detectors."

**Dogfood pass + coverage follow-up (`74d56e1` + branch `coverage-followup`):** First end-to-end run against real Terraform (govnotes-demo) rather than hand-crafted fixtures. Ground-truth hit rate: 3/12 → 5/12 full-catch after the two P1 detectors below landed; 5/12 → 7/12 counting partials. Headline finding: Terraform module `for_each` blind spot — parser sees 1 bucket where govnotes declares 5 through a storage module's map, invisible until Plan JSON support lands. Full report + P0/P1/P2/P3 follow-up backlog in `docs/dogfood-2026-04-22.md`.
- `aws.encryption_ebs` — SC-28 / SC-28(1), `ksis=[]`. Scans `aws_ebs_volume` + `aws_instance.{root,ebs}_block_device`, emits per-block Evidence so mixed postures (encrypted root + unencrypted data) are visible.
- `aws.iam_user_access_keys` — IA-2 / AC-2, `ksis=[KSI-IAM-MFA]`. Flags every declared `aws_iam_access_key` as a posture gap; claims KSI-IAM-MFA because access keys bypass MFA by design (applying the Phase 6-lite discipline: control membership AND statement-evidencing).

**Plan JSON source-expansion (`79c25db`, `8774727`, `34e6755`, `5895df7`):** Design entry + Phase A implementation + Phase B equivalence testing of Terraform Plan JSON support — dogfood finding P0. Users generate plan JSON as part of their CI (`terraform plan -out X && terraform show -json X > plan.json`) and pass it to `efterlev scan --target . --plan FILE`. The translator (`efterlev.terraform.parse_plan_json`) normalizes plan-JSON resources into the same `TerraformResource` shape HCL parsing produces, so every existing detector runs against plan-derived resources without modification. Second dogfood re-run against govnotes: hit rate 5/12 → **8/12 full-catch** (gap #1 `user_uploads` encryption now visible via module-expansion; gap #7 `readonly_auditor` MFA visible because plan JSON resolves the `jsonencode(data.aws_iam_policy_document…)` expression at plan time — the existing detector's static-JSON path just works, zero detector changes). Partial+full: 7/12 → 10/12. Phase B equivalence tests cover all 14 detectors against per-detector `.plan.json` fixtures (Terraform CLI NOT a test dependency). Full design call: DECISIONS 2026-04-22 "Design: Terraform Plan JSON support."

**External-review honesty pass (`24b8b2b`, `f0567fa`, `69873a0`, branch `review-followup-honesty`):** A 2026-04-23 external grep-level audit caught five cases where docs claimed features the code didn't implement — direct violation of Principle 1 ("Evidence before claims") applied to our own documentation. Resolved in three commits: (a) rewrote `THREAT_MODEL.md` secrets/T3/T5 sections to describe current state honestly (no secret redaction pass today — evidence content reaches the LLM verbatim; per-agent fence-citation validators are the primary Claim-integrity enforcement, not a mythical `validate_claim_provenance` primitive), fixed `README.md` stale counts + `pipx install` references, fixed `CONTRIBUTING.md` detector tutorial to match DECISIONS 2026-04-21 discipline; (b) removed dead `config.llm.fallback_model` field (written but never read); (c) implemented `provenance show` source-ref-at-evidence-leaves rendering so chain walks surface `source=main.tf:12-18` not just `content_ref=<blob>`. Deferred-but-documented: secret redaction impl, retry+fallback impl, store-write-time `validate_claim_provenance`, `mcp list` subcommand. All listed in `LIMITATIONS.md`'s new "Known gaps between documentation and code" section. Full design call: DECISIONS 2026-04-23 "External deep-review honesty pass."

**Secret redaction before LLM transmission (branch `secret-redaction`):** The 2026-04-23 review's highest-leverage v1.x item, now implemented. A pattern library in `src/efterlev/llm/scrubber.py` catches 7 structural secret families (AWS access keys, GCP API keys, GitHub tokens, Slack tokens, Stripe keys, PEM private keys, JWT-shape tokens), each with documented provenance. `scrub_llm_prompt(text, context_hint)` replaces matches with `[REDACTED:<kind>:sha256:<8hex>]` tokens that preserve field shape for model reasoning without exposing the value. Hook point: `format_evidence_for_prompt` and `format_source_files_for_prompt` in `agents/base.py` call the scrubber unconditionally before fencing — fail-closed on scrubber exception. Optional `RedactionLedger` audit sink captures every match with `{timestamp, pattern_name, sha256_prefix, context_hint}` (never the secret). 23 unit tests + 10 adversarial integration tests lock the behavior in. Dogfood against real govnotes: 0 false-positive redactions (ARNs, resource names, KMS paths all pass through); seeded AWS key → correctly caught. THREAT_MODEL.md rewritten to describe the implemented pass. Follow-up: ledger-to-disk wiring + `efterlev redaction review` CLI (audit sugar; the security property already holds). Full design call: DECISIONS 2026-04-23 "Secret redaction implementation."

**Retry + Opus-to-Sonnet fallback (branch `retry-fallback`):** `AnthropicClient.complete()` previously raised immediately on every `anthropic.*` exception — a single transient 529 during a 60-KSI Gap run lost the whole scan. Now: up to 3 retries with exponential backoff + full jitter on transient errors (`RateLimitError` 429, `APITimeoutError`, `APIConnectionError`, `InternalServerError` 5xx/529). Non-retryable errors (401/400/403/404) bypass the retry loop entirely. After primary-model retries exhaust, ONE attempt on the `fallback_model` (default `claude-sonnet-4-6`) before surfacing the original error. `LLMConfig.fallback_model` returned to config with a disable-by-empty-string semantic. `LLMResponse.model` carries the served model through to provenance, so a chain inspected later accurately shows "this Gap classification was served by Sonnet after Opus retries exhausted." Injectable `sleeper` keeps tests sub-second. 13 unit tests lock the behavior in. Full design call: DECISIONS 2026-04-23 "Retry + Opus-to-Sonnet fallback."

**Redaction audit log + `efterlev redaction review` CLI (branch `redaction-audit`):** Follow-up to the secret-redaction commit; adds the audit trail users and reviewers need to confirm what got redacted during any given scan. `active_redaction_ledger(ledger)` context manager mirrors `active_store`; each agent CLI command threads a ledger via contextvar, writes to `.efterlev/redacted.log` (JSONL, 0600 perms) at end-of-scan, echoes a one-line summary. `efterlev redaction review [--scan-id X] [--limit N]` reads the log and prints per-scan summaries or per-event detail. 15 tests lock in perm semantics, contextvar lifecycle, kwarg-wins-over-active precedence, and CLI output shapes. Full design call: DECISIONS 2026-04-23 "Redaction audit log + `efterlev redaction review` CLI."

**POA&M markdown output primitive + `efterlev poam` CLI (branch `poam-output`):** First new customer-facing output format since FRMR attestation. Deterministic (no LLM call) transformation of Gap Agent classifications + FRMR catalog → POA&M markdown. Only `partial` and `not_implemented` KSIs become items (closed classifications have no remediation plan). Severity heuristic: not_implemented → HIGH, partial → MEDIUM, marked explicitly as starting-point-heuristic-reviewer-adjustable. Every Reviewer field (Weakness Title, Remediation Plan, Milestones, Target Completion Date, Owner, POC Email, Residual Risk, Risk Accepted) emits as `DRAFT — SET BEFORE SUBMISSION` — grep-for-unfilled trivially. POA&M IDs derive from claim_record_id when available (`POAM-<KSI>-<first-8-of-claim>`) for provenance-graph anchor; fall back to positional id otherwise. Unknown-KSI classifications skipped, not fabricated (same posture as `generate_frmr_attestation`). 18 tests; dogfood against govnotes plan-mode scan produces a 59-item POA&M with populated FRMR KSI names + correct severity heuristic. Full design call: DECISIONS 2026-04-23 "POA&M markdown output primitive."

**GitHub Action for PR-level compliance scan (branch `github-action`):** The 2026-04-23 review's "should be month 1" recommendation. `.github/workflows/pr-compliance-scan.yml` runs on any PR touching `.tf`, `.tfvars`, or `.efterlev/manifests/` — installs Efterlev via `uv sync`, runs init+scan, optionally runs `agent gap` gated on `ANTHROPIC_API_KEY`, calls `scripts/ci_pr_summary.py` to render a markdown PR comment, posts-or-updates a sticky comment identified by its `## 🧪 Efterlev compliance scan` header, and uploads `.efterlev/reports/` as a workflow artifact. Summarizer reads the SQLite DB + blob store directly (not via Python API) so the CI-shell/virtualenv split doesn't break imports. 21 tests lock in the finding classifier, markdown shape, and DRAFT-disclaimer inclusion. `--fail-on-finding` flag for orgs that want CI gating. `docs/ci-integration.md` documents the drop-in flow for consumer repos. Deferred: regression detection (diff vs base branch), per-line PR annotations, composite action + Marketplace listing (lands with PyPI release as part of pre-launch readiness gate A2 per DECISIONS 2026-04-23 "Rescind closed-source lock"). Full design call: DECISIONS 2026-04-23 "GitHub Action for PR-level compliance scan."

**Store-level `validate_claim_provenance` (branch `validate-claim-provenance`):** Defense-in-depth for the claim-citation integrity story. `ProvenanceStore.write_record` now validates every Claim's `derived_from` at write time: each cited id must resolve as either a `ProvenanceRecord.record_id` OR an `Evidence.evidence_id` in a stored evidence payload. Unresolvable ids raise `ProvenanceError` BEFORE insertion — the rejected record never lands. Per-agent `_validate_cited_ids` fence-citation helpers remain the primary enforcement (catches model-hallucinated sha256s against the prompt's nonced fences); this store-level check is secondary, catching agent bugs or direct-store-write paths that bypass the agent layer. Dual-keyed lookup exists because Evidence.evidence_id (Evidence-content hash) differs from the ProvenanceRecord.record_id of the envelope that stored it (envelope-content hash including metadata + timestamp). Two-step lookup (indexed record_id query + fallback evidence-payload scan) keeps the common case O(1). 11 new validator tests + 13 existing test updates (tests now persist evidence to the store before invoking agents, matching real CLI flow). Full design call: DECISIONS 2026-04-23 "Store-level validate_claim_provenance."

**End state at 2026-04-23:**
- 460 tests passing (+ 1 E2E skipped by default without `ANTHROPIC_API_KEY`).
- ruff clean; mypy strict-clean on 96 source files (strict on `efterlev.{primitives,detectors,oscal,manifests}.*`).
- 14 detectors registered (6 v0 + 6 Phase 6-lite + 2 coverage-followup); 8 declare a KSI mapping and 6 surface at the 800-53 level only per the SC-28 Option-C precedent (DECISIONS 2026-04-21 design call #1). The ksis=[] posture is the honest default when no FRMR KSI maps the relevant control, and Phase 6-lite formalized a second discipline: control membership in a KSI's FRMR `controls` array is necessary but not sufficient for claiming that KSI — the detector must also evidence what the KSI's *statement* commits to.
- Two scan modalities: HCL-directory (`--target DIR`) for local dev; plan JSON (`--plan FILE`) for CI. Both modalities flow Evidence through the same detectors and the same provenance store; downstream (agents, renderers) is modality-agnostic.
- Full pipeline verified end-to-end against a real Opus 4.7 call: Gap (60-KSI classification, 88s), Documentation (per-KSI Sonnet 4.6 narratives, ~7min), Remediation (diff-shaped output, 13s). 12/13 critical checks pass, 5/5 quality checks pass.
- Three deterministic output formats: `generate_frmr_attestation` (FRMR-shaped JSON), `generate_frmr_skeleton` (per-KSI scanner-only draft), `generate_poam_markdown` (remediation-tracking markdown). All byte-stable, typed-Pydantic-validated, DRAFT-marked where applicable.
- **Secret redaction before LLM transmission is implemented and unconditional**: 7 pattern families, fail-closed, audit log at `.efterlev/redacted.log` with `efterlev redaction review` CLI for review.
- **Reliability: transient Anthropic errors are retried (3x, exponential+jitter) with Opus-to-Sonnet fallback** on exhaustion. Non-retryable errors still surface immediately.

**End state at 2026-04-25 — all eight pre-launch readiness gates closed at the spec level (DECISIONS 2026-04-25 "A1-A8 buildout"):**
- 602 tests passing (+142 from the A1-A8 sweep). ruff clean; mypy strict-clean on 129 source files. mkdocs strict build exit 0; `scripts/launch-grep-scrub.sh` clean; `pip-audit` clean (runtime + dev).
- A1 (identity & licensing) — Apache-2.0, CODE_OF_CONDUCT, GOVERNANCE (BDFL-now / collective-later), PyPI name held, GitHub org `efterlev` claimed, `efterlev.com` reserved.
- A2 (distribution & packaging) — `pyproject.toml` PyPI metadata, Dockerfile + `release-container.yml` (Sigstore keyless OIDC + cosign), `release-pypi.yml` (trusted publishing), `release-smoke.yml` install matrix, `scripts/verify-release.sh`, `docs/RELEASE.md` template.
- A3 (Bedrock backend, SPEC-10) — `LLMClient` protocol with `AnthropicClient` + `AnthropicBedrockClient` via Converse API; `[bedrock]` extra opt-in; `tests/test_e2e_smoke_bedrock.py` covers the Bedrock pipeline; GovCloud regional-endpoint walkthrough at `docs/deploy-govcloud-ec2.md`.
- A4 (30 detectors, SPEC-14) — 16 net-new AWS detectors landed under `src/efterlev/detectors/aws/<capability>/` (each five-file: detector.py, mapping.yaml, evidence.yaml, fixtures/, README.md), bringing the catalog from 14 to 30.
- A5 (trust surface, SPEC-30) — CODEOWNERS + BRANCH_PROTECTION.md + SIGNING_KEYS.md, dependabot for pip + actions + docker, ISSUE_TEMPLATE/* + PR template, `ci-security.yml` (pip-audit + bandit + semgrep + CodeQL), and `docs/security-review-2026-04.md` populated through §7 awaiting maintainer §8 sign-off.
- A6 (docs site, SPEC-38) — Material strict-mode mkdocs config, full nav (concepts/tutorials/comparisons/reference), `docs-deploy.yml` GitHub Pages workflow with `workflow_dispatch` for the post-flip first-deploy.
- A7 (deployment-mode matrix, SPEC-53) — 15-mode green/yellow/white-circle matrix with manual-verification runbook template.
- A8 (launch rehearsal, SPEC-56) — `scripts/launch-grep-scrub.sh` + allowlist (clean), `docs/launch/runbook.md` (fresh-eyes-walked 2026-04-25, four operational papercuts fixed), `docs/launch/failure-response.md`, `docs/launch/announcement-copy.md`, `docs/launch/design-partner-outreach.md`.

**What's left before the public flip (maintainer-action queue):**
- Repo transfer `lhassa8/Efterlev` → `efterlev/efterlev`.
- Apply branch protection per `.github/BRANCH_PROTECTION.md` on the destination repo.
- Enable GitHub Pages (Source: GitHub Actions) on the destination while still private.
- Docker Hub `efterlev` org claim, npm namespace hold, DCO bot install on the org.
- PyPI Trusted Publishing config pointed at `efterlev/efterlev`.
- Maintainer §8 sign-off on `docs/security-review-2026-04.md`.
- 24-hour pause + fresh-eyes walk through `docs/launch/runbook.md` (one human, one read).
- GovCloud walkthrough by a maintainer with hands-on AWS GovCloud access (one of the 15 deployment modes that needs hands-on verification before promoting from ⚪ → 🟡).

**What's next (post-launch, Phase C — written just-in-time per the hybrid spec policy):**
- CI regression detection (scan PR + base branch, diff evidence) — biggest follow-up to the GitHub Action.
- Unify `derived_from` semantics on `record_id` only (the dual-keyed lookup is a pragmatic bridge).
- Context-aware high-entropy redaction patterns (`password\s*=\s*"..."` shapes) as a second-pass secret detection layer.
- POA&M integration with Remediation Agent output (enrich Remediation Plan field from prior `agent remediate` runs).
- Phase 4 (runtime + drift) — gated on having enough scans-over-time data; may wait for first prospect usage.
- Phase 5 (review workflow, manifest-staleness prompt-layer treatment).
- Real PR creation against real repos (Drift Agent / `--apply` flag — explicit and opt-in).
- mkdocs-material blog plugin enable (the "Why we built Efterlev" docs-site post is on dev.to + Medium for v0.1.0; docs-site blog is v0.2.0).

---

## Non-negotiable principles

These override local convenience. If you feel tempted to violate one, stop and ask.

1. **Evidence before claims.** Deterministic scanner output is primary, high-trust, and citable. LLM-generated content (narratives, mappings, rankings, remediation proposals) is secondary, carries confidence levels, and is explicitly marked "DRAFT — requires human review" in output. The two classes are visible in the data model, the FRMR output, and every rendered report.
2. **Provenance or it didn't happen.** Every generated claim — finding, narrative, mapping, remediation — emits a provenance record linking it to its upstream sources (detector output, evidence records, LLM calls). No exceptions, not for speed, not for demo polish.
3. **FRMR as primary output; OSCAL as secondary v1 output. Internal model is KSI-shaped.** The user-facing layer is Indicators (KSIs) and Themes; 800-53 Controls remain first-class because KSIs reference them, but they are the underlying layer, not the primary surface. FRMR-compatible JSON is what the Documentation Agent produces at v0. OSCAL output generators are v1 additions for users transitioning Rev5 submissions and for downstream OSCAL-Hub-style consumers. The internal data model is our own Pydantic types, shaped around our needs; FRMR and OSCAL are both produced at the output boundary, not used as internal representations.
4. **Detectors are the moat; primitives are the interface.** The detection library is a community-contributable asset. Each detector is a self-contained folder a contributor can add without touching the rest of the codebase. Primitives are the stable, MCP-exposed surface over which agents reason.
5. **Agent-first, pragmatically.** Every primitive is exposed via our MCP server from the moment it exists. External agents (other people's Claude Code, third-party tools) can discover and call every primitive. Our own agents prefer the MCP interface because it proves the architecture, but direct Python imports are acceptable when they materially improve performance or reliability. Don't be religious about it; the useful, demoable solution is what matters.
6. **Demo a slice, architect for the whole.** The MVP is narrow (six controls, one cloud, one IaC tool). The architecture must make adding the next 50 detectors obvious, not painful.
7. **Drafts, not authorizations.** Efterlev never claims to produce an ATO, a pass, or a guarantee of compliance. It produces drafts that accelerate the human/3PAO process. This is not hedging; it's the truth, and it's the only claim that survives serious scrutiny.

---

## Tech stack

- **Language:** Python 3.12
- **Dependency management:** `uv`
- **Typing:** Pydantic v2 for all primitive I/O. No untyped dicts crossing a primitive boundary.
- **FRMR:** `FRMR.documentation.json` vendored from `FedRAMP/docs` into `catalogs/frmr/`. It is a single authoritative JSON file (`info`, `FRD`, `FRR`, `KSI`) — substantially simpler than OSCAL's nested model hierarchy. Load with Pydantic directly; no specialized library required. **Validation:** on load, validate the vendored catalog against `FedRAMP.schema.json` (JSON Schema draft 2020-12) before acceptance. On output, attestation artifacts use Pydantic structural validation (`extra="forbid"` + strict literals) at construction time — FedRAMP has not published an attestation-output schema as of April 2026, so `FedRAMP.schema.json` does not apply to our output. See DECISIONS 2026-04-22 "Phase 2: FRMR attestation generator" for the schema-posture call and the follow-up for an external `efterlev-attestation.schema.json` mirror.
- **OSCAL (v0 input only):** `compliance-trestle` for loading the vendored NIST SP 800-53 Rev 5 catalog, which every KSI indicator references via its `controls` field. Trestle is not used for FedRAMP-specific profiles (no current upstream source after the GSA/fedramp-automation archive). OSCAL *output* generation is a v1 roadmap item; hand-rolled Pydantic generators where trestle's generation APIs are clunky — document reason in `DECISIONS.md`.
- **MCP:** Official Anthropic Python SDK for MCP server authoring. Stdio transport.
- **Agent inference:** Anthropic Python SDK. Default model `claude-opus-4-7`. Switch to `claude-sonnet-4-6` only if we hit latency issues during demo. **Centralize client instantiation in `src/efterlev/llm/__init__.py` — do not scatter `anthropic.Anthropic()` calls across agent files.** This is the cheap hedge for the v1 pluggable-backend work; see `DECISIONS.md`.
- **LLM backends (v1):** AWS Bedrock committed as the second backend via an `LLMClient` abstraction. This is not a hackathon deliverable — v0 wires to the Anthropic SDK directly — but v0 code structure must not foreclose it.
- **Storage:** SQLite for the provenance graph and metadata. Content-addressed blob store on disk under `.efterlev/store/` (SHA-256 filenames). Timestamped and versioned — evidence records are appended, never overwritten.
- **CLI:** Typer. Single entry point: `efterlev`.
- **IaC parsing:** `python-hcl2` for Terraform.
- **Code scanning:** `semgrep` via subprocess.
- **Testing:** `pytest`. Every primitive and detector has ≥1 happy-path and ≥1 error-path test. No coverage targets — we optimize for confidence, not numbers.
- **Formatting:** `ruff` for lint + format. `mypy --strict` on `src/efterlev/primitives/`, `src/efterlev/detectors/`, `src/efterlev/frmr/`, `src/efterlev/oscal/`.
- **Docs:** MkDocs Material.

---

## Repository layout

```
efterlev/
├── CLAUDE.md                          # this file
├── README.md                          # user-facing
├── CONTRIBUTING.md                    # human-contributor onboarding
├── DECISIONS.md                       # running log of non-trivial choices — APPEND-ONLY
├── LIMITATIONS.md                     # judge-facing + user-facing
├── THREAT_MODEL.md                    # security posture
├── COMPETITIVE_LANDSCAPE.md           # honest positioning
├── LICENSE                            # Apache 2.0
├── docs/
│   ├── dual_horizon_plan.md           # the full plan
│   ├── architecture.md
│   ├── scope.md
│   └── primitives.md                  # auto-generated from decorator metadata
├── src/efterlev/
│   ├── models/                        # our internal Pydantic types
│   │   ├── indicator.py               # Indicator (a KSI), Theme, Baseline
│   │   ├── control.py                 # Control, ControlEnhancement (800-53, referenced by KSIs)
│   │   ├── evidence.py                # Evidence (deterministic)
│   │   ├── claim.py                   # Claim (LLM-reasoned)
│   │   ├── finding.py
│   │   ├── mapping.py
│   │   ├── provenance.py
│   │   └── attestation_draft.py       # internal AttestationDraft before FRMR serialization
│   ├── frmr/                          # FRMR loader + validator + generator (primary output)
│   ├── oscal/                         # 800-53 catalog loader via trestle; OSCAL generator is v1
│   ├── detectors/                     # the detection library (community-contributable)
│   │   ├── base.py                    # Detector base class + decorator
│   │   └── aws/
│   │       ├── encryption_s3_at_rest/
│   │       │   ├── detector.py
│   │       │   ├── mapping.yaml
│   │       │   ├── evidence.yaml      # our internal schema, not FRMR or OSCAL
│   │       │   ├── fixtures/          # should-match + should-not-match samples
│   │       │   └── README.md
│   │       └── ...
│   ├── primitives/                    # MCP-exposed agent-legible capabilities
│   │   ├── scan/
│   │   ├── map/
│   │   ├── evidence/
│   │   ├── generate/                  # FRMR + HTML generators at v0; OSCAL generator in v1
│   │   └── validate/
│   ├── mcp_server/
│   ├── agents/
│   │   ├── base.py
│   │   ├── gap.py                     # + gap_prompt.md
│   │   ├── documentation.py           # + documentation_prompt.md
│   │   └── remediation.py             # + remediation_prompt.md
│   ├── provenance/
│   └── cli/
├── catalogs/                          # inputs: FRMR + 800-53 Rev 5 catalog
│   ├── frmr/                          # FedRAMP FRMR JSON + schema
│   └── nist/                          # NIST SP 800-53 Rev 5 catalog (OSCAL JSON)
├── demo/govnotes/                     # sample target app
└── tests/
```

When adding new detectors, match the cloud/source folder. When adding primitives, match the capability verb (`scan`, `map`, `evidence`, `generate`, `validate`). If it doesn't fit, propose a new subfolder in chat before creating it.

---

## The detector contract

A detector is a self-contained artifact. One folder per detector. A contributor can add a new detector without reading the rest of the codebase. This is the #1 design commitment for long-term project health.

Each detector folder contains:

- **`detector.py`** — pure function, typed input/output. Reads source material (IaC files, manifests, etc.), emits `Evidence` records.
- **`mapping.yaml`** — which KSI(s) this detector evidences, plus the underlying 800-53 control(s) those KSIs reference. Multi-target mappings are fine (one detector can evidence multiple KSIs and multiple controls).
- **`evidence.yaml`** — template describing the shape and semantics of evidence this detector produces. Our internal schema, not FRMR or OSCAL.
- **`fixtures/`** — `should_match/` and `should_not_match/` IaC samples the test harness runs against.
- **`README.md`** — human-readable: what this detector checks, what it proves, what it does not prove, known limitations.

Detector IDs are capability-shaped (what the detector checks), not control-shaped. KSIs think in capabilities; IDs like `encryption_s3_at_rest` age better than IDs like `sc_28_s3_encryption` as the KSI ↔ control mapping evolves.

Example:

```python
# detectors/aws/encryption_s3_at_rest/detector.py
from efterlev.detectors.base import detector
from efterlev.models.evidence import Evidence

@detector(
    id="aws.encryption_s3_at_rest",
    ksis=["KSI-SVC-VRI"],             # Validating Resource Integrity (nearest KSI; see README.md)
    controls=["SC-28", "SC-28(1)"],   # underlying 800-53 controls
    source="terraform",
    version="0.1.0",
)
def detect(tf_resources: list[TerraformResource]) -> list[Evidence]:
    """
    Detect S3 bucket encryption configuration at rest.

    Evidences (800-53):  SC-28 (Protection at Rest), SC-28(1) (Cryptographic Protection).
    Evidences (KSI):     KSI-SVC-VRI (Validating Resource Integrity) — partial.
    Does NOT prove:      key management practices, rotation, BYOK — those are
                         SC-12/SC-13 / KSI-SVC-ASM territory. This detector only
                         evidences the infrastructure layer of at-rest encryption,
                         not the procedural layer.

    Note: FRMR 0.9.43-beta does not list SC-28 in any KSI's `controls` array, so
    the KSI mapping above is a judgment call grounded in FedRAMP's stated intent
    (cryptographic means to prevent unauthorized access to federal customer data
    at rest). Re-evaluate when FRMR GA ships.
    """
    ...
```

The docstring's "does NOT prove" section is required. This is the evidence-vs-claims discipline at the detector level — we name what we've actually verified and what we haven't.

---

## The primitive contract

Primitives are the MCP-exposed agent interface. ~15–25 total at v1. Small and stable.

**Two classes of primitives, different contracts:**

**Deterministic primitives** — scan, map, validate, parse, hash, serialize. Pure where possible. Side-effecting primitives (write files, open PRs) are flagged. Tests cover happy path + edge cases. Example:

```python
@primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
def scan_terraform(input: ScanTerraformInput) -> ScanTerraformOutput:
    """Run all applicable detectors against a Terraform source tree."""
```

**Generative primitives** — narrative synthesis, mapping proposal, remediation suggestion. LLM-backed. Output carries confidence levels and a "requires human review" flag. Tests are harder; we use snapshot comparisons and known-good fixtures. Example:

```python
@primitive(capability="generate", side_effects=False, version="0.1.0", deterministic=False)
def generate_ssp_narrative(input: GenerateNarrativeInput) -> GenerateNarrativeOutput:
    """Draft SSP narrative for a control, grounded in its evidence records."""
```

**Shared rules for both classes:**

- Verb-noun snake_case name
- One Pydantic input model, one Pydantic output model
- Docstring states intent, side effects, deterministic/generative, external dependencies
- Emits a provenance record via decorator machinery — you do not write provenance code inside the function body
- Auto-registered with the MCP server by the decorator
- No `print`; use the standard logger
- Raises typed exceptions from `efterlev.errors`, never bare `Exception`
- Before adding a new primitive, check `docs/primitives.md` for overlap. If something close exists, extend or rename — don't add a parallel function.

---

## The agent contract

Every agent:

- Subclasses `efterlev.agents.base.Agent`
- Has a system prompt in a sibling `.md` file (e.g. `gap.py` → `gap_prompt.md`). Prompts are product code. Do not inline them as Python strings.
- Consumes primitives via the MCP tool interface by default. Direct imports from `efterlev.primitives.*` are allowed when MCP round-tripping adds no value; flag the choice in the agent's docstring.
- Produces a typed output artifact on our internal model (e.g. `GapReport`, `AttestationDraft`, `RemediationProposal`). FRMR and OSCAL serialization are separate generator steps, not the agent's job.
- Logs every tool call, model response, and final artifact to the provenance store
- Is invokable standalone from the CLI: `efterlev agent <n> [options]`

**When you write or revise an agent's system prompt, surface the full diff in chat for review before committing.** Agent prompts are the product's brain; they deserve human sign-off even when code doesn't.

---

## Evidence vs. claims: the data model

Two distinct types, treated differently throughout the system.

```python
class Evidence(BaseModel):
    """Deterministic, scanner-derived, high-trust."""
    evidence_id: str                    # sha256 of canonical content
    detector_id: str                    # "aws.encryption_s3_at_rest"
    ksis_evidenced: list[str]           # ["KSI-SVC-VRI"] — primary indicator(s)
    controls_evidenced: list[str]       # ["SC-28", "SC-28(1)"] — underlying 800-53
    source_ref: SourceRef               # file + line + commit hash
    content: dict                       # detector-schema-shaped
    timestamp: datetime

class Claim(BaseModel):
    """LLM-reasoned, requires human review."""
    claim_id: str                       # sha256 of canonical content
    claim_type: Literal["narrative", "mapping", "remediation", "classification"]
    content: str | dict
    confidence: Literal["low", "medium", "high"]
    requires_review: bool = True        # always true at v0
    derived_from: list[str]             # evidence_ids and/or other claim_ids
    model: str                          # "claude-opus-4-7"
    prompt_hash: str                    # hash of the system prompt used
    timestamp: datetime
```

Every rendered output — HTML report, FRMR artifact, OSCAL artifact, terminal summary — visually distinguishes Evidence from Claims. Evidence cites raw sources. Claims carry the "DRAFT — requires human review" marker. An auditor reading our output can always tell which is which.

---

## Provenance model

Every claim is a node in a directed provenance graph. Edges point from derived claims to upstream sources.

```python
class ProvenanceRecord(BaseModel):
    record_id: str                      # sha256 of canonical content
    record_type: Literal["evidence", "claim", "finding", "mapping", "remediation"]
    content_ref: str                    # path in blob store
    derived_from: list[str]             # upstream record_ids (evidence or claim)
    primitive: str | None               # "scan_terraform@0.1.0"
    agent: str | None                   # "gap_agent" if agent-mediated
    model: str | None                   # "claude-opus-4-7" if LLM-involved
    prompt_hash: str | None             # hash of system prompt if LLM-involved
    timestamp: datetime
    metadata: dict
```

Rules:
- A record with `derived_from=[]` is raw evidence or a primitive input. Any reasoning step must carry its inputs forward.
- Records are immutable and append-only. New evidence for a KSI creates a new record; it does not overwrite the old one. This supports the v1 drift-detection story.
- `efterlev provenance show <record_id>` walks the chain. Every new record type must render sensibly.

When you implement a primitive or agent that generates records, **write the provenance walk test first**. If the chain doesn't resolve end-to-end, the feature isn't done.

---

## FRMR and OSCAL conventions

FRMR is the primary output format at v0. OSCAL is a secondary output format planned for v1. Both are **output**, not internal representations.

**FRMR (primary, v0):**

- **Input:** `catalogs/frmr/FRMR.documentation.json` vendored from `FedRAMP/docs`. Loaded with Pydantic at startup into our internal `Indicator`, `Theme`, and related types. KSI indicators' `controls` fields tie each KSI to one or more 800-53 controls, which the 800-53 loader resolves.
- **Output:** FRMR-compatible JSON artifacts (primarily `AttestationDraft`-shaped validation data) produced by dedicated generator primitives in `primitives/generate/`. Plus HTML and markdown alongside.
- **Validation:** Every generated FRMR artifact is validated against `catalogs/frmr/FedRAMP.schema.json` before return. `efterlev.primitives.validate.validate_frmr` is called inside the generator — if validation fails, the generator raises.

**OSCAL (input at v0, output at v1):**

- **Input:** NIST SP 800-53 Rev 5 catalog at `catalogs/nist/` is loaded via `compliance-trestle` into our internal `Control` and `Catalog` types. FedRAMP-specific OSCAL profiles are not loaded at v0; no current canonical upstream source after the GSA/fedramp-automation archive.
- **Output (v1):** OSCAL Assessment Results, partial SSP, POA&M generators are roadmap items for Rev5 transition users. Validation against the NIST OSCAL schemas will run inside the generator before return.

When in doubt about FRMR modeling, default to the structure described in `catalogs/frmr/FRMR.md`. When OSCAL generators land in v1 and you need reference material, the `usnistgov/oscal-content` repo holds the canonical examples.

---

## Detection scope (hackathon MVP — locked)

Six detection areas. **Do not add areas outside this set without asking** — scope creep here is how we lose the hackathon.

KSIs below are from FRMR 0.9.43-beta (vendored at `catalogs/frmr/FRMR.documentation.json`). Each detection area evidences one or more KSIs and the underlying 800-53 controls those KSIs reference.

| Detection area | KSI (FRMR 0.9.43-beta)                          | 800-53         | Signal source             |
| -------------- | ----------------------------------------------- | -------------- | ------------------------- |
| Encryption at rest | `[TBD]` — closest: KSI-SVC-VRI (Validating Resource Integrity); see note below | SC-28, SC-28(1) | S3/RDS/EBS encryption     |
| Transmission confidentiality | KSI-SVC-SNT (Securing Network Traffic)  | SC-8           | TLS config, ALB listener  |
| Cryptographic protection | KSI-SVC-VRI (Validating Resource Integrity); also reinforces KSI-SVC-SNT | SC-13          | Algorithms, FIPS mode     |
| MFA enforcement | KSI-IAM-MFA (Enforcing Phishing-Resistant MFA) | IA-2           | IAM policy conditions     |
| Event logging & audit generation | KSI-MLA-LET (Logging Event Types), KSI-MLA-OSM (Operating SIEM Capability) | AU-2, AU-12 | CloudTrail scope          |
| System backup | KSI-RPL-ABO (Aligning Backups with Objectives)    | CP-9           | RDS backups, S3 versioning|

**On the SC-28 / encryption-at-rest `[TBD]`:** FRMR 0.9.43-beta does not list SC-28 in any KSI's `controls` array, and no indicator's `statement` mentions "at rest" explicitly. KSI-SVC-VRI ("Use cryptographic methods to validate the integrity of machine-based information resources") is the nearest thematic fit — it lives in the Service Configuration theme whose overview references "FedRAMP encryption policies" — but it nominally maps to SC-13 (integrity via crypto), not SC-28 (confidentiality of data at rest). Treat the mapping as a judgment call pending resolution. Day 1 should either: (a) accept KSI-SVC-VRI with an honest docstring caveat, (b) propose the detection area be reframed around integrity rather than confidentiality, or (c) surface the gap to FedRAMP via an issue on `FedRAMP/docs`. Do not invent a KSI that does not exist.

**On KSI-IAM-MFA:** the indicator requires *phishing-resistant* MFA (FIDO2/WebAuthn tier). Our detector only proves the IAM policy condition `aws:MultiFactorAuthPresent` is enforced. That's MFA-presence, not phishing-resistance. The detector README must name this gap.

**On KSI-RPL-ABO:** the indicator is about *alignment* of backups with recovery objectives — a claim about intent, not just mechanics. Our detector proves backups are enabled; "aligned with objectives" requires procedural evidence we cannot see from Terraform.

These detection areas were chosen because the infrastructure layer is genuinely dispositive — a detector can honestly say "the encryption configuration is present" without overclaiming the full KSI (including the procedural aspects). Detector `README.md` files must name the layer they evidence and the layer they do not.

**Explicitly deferred to v1+ as detectors:**

- AC-2, AC-6, AC-17 (identity/access controls requiring procedural evidence)
- AU-3 (audit record content — requires log schema inspection)
- CM-2, CM-6 (baseline configuration — requires procedural evidence)
- RA-5, SI-2, SI-4 (vulnerability management and monitoring)
- SC-7 (boundary protection — partially detectable but complex)
- All AT-\*, PL-\*, PS-\*, PM-\* (pure policy/procedural controls)
- Any control requiring runtime cloud API calls (v1+)

**Partially covered by Phase 6-lite (landed 2026-04-22):**

- AC-3 — `aws.s3_public_access_block` evidences infrastructure-layer
  public-access-block posture on S3 buckets; broader access-enforcement
  coverage (IAM Access Analyzer, bucket policies, etc.) is Phase 6-full.
- IA-5, IA-5(1) — `aws.iam_password_policy` evidences the account-level
  password-policy declaration; per-user MFA is the separate
  `mfa_required_on_iam_policies` detector.
- SC-12, SC-12(2) — `aws.kms_key_rotation` evidences automatic CMK
  rotation on symmetric keys.
- AU-9 — `aws.cloudtrail_log_file_validation` evidences CloudTrail
  log-file-integrity digests.

Phase 1 Evidence Manifests (`.efterlev/manifests/*.yml`, landed 2026-04-22) are the complement: procedural controls in this list that have no Terraform-detectable surface can be covered by customer-authored, human-signed attestations that flow into the Gap Agent as `Evidence(detector_id="manifest")` alongside detector Evidence. Manifests do NOT replace detectors where a detector is practical (IAM policy MFA, CloudTrail scope, etc.) — they cover the procedural layer detectors cannot see. See DECISIONS 2026-04-22 "Phase 1: Evidence Manifests" for the full design call.

---

## What we are explicitly NOT building (hackathon)

Refuse scope expansions into:
- Input sources other than Terraform/OpenTofu (`.tf` files). No CloudFormation, AWS CDK, Pulumi, Kubernetes manifests, or runtime cloud API scanning at v0. All are v1 priorities, sequenced in `docs/dual_horizon_plan.md` §3.1.
- Real cloud account scanning (we read Terraform, we don't call AWS APIs)
- Continuous monitoring / drift daemon (v1)
- Adversarial Auditor Agent (v1 roadmap)
- Cross-framework mapping beyond FedRAMP 20x Moderate (CMMC 2.0 is the v1 second framework)
- GDPR, HIPAA, PCI, SOC 2, ISO 27001 (explicitly out — different tools do this)
- **OSCAL output generators at v0.** FRMR is the v0 primary output. OSCAL generation lands in v1 for users transitioning Rev5 submissions and for OSCAL-Hub-style downstream consumers.
- Web UI beyond generated static HTML reports
- Authentication/multi-tenancy (local CLI tool only)
- Real PR creation against real repos (local diff generation is the hackathon demo)

If the user asks for any of these, point to this list and confirm they want to trade it against an MVP item.

---

## Quality bar

- **Every detector:** typed I/O, docstring with "proves/does not prove," fixtures for should-match and should-not-match, passing tests.
- **Every primitive:** typed I/O, docstring, ≥1 happy test, ≥1 error test, FRMR (and in v1, OSCAL) validation on output where applicable, provenance record emitted.
- **Every agent:** system prompt in its own file, provenance-emitting, CLI-invokable, one end-to-end test against the demo repo.
- **Every commit:** `ruff` clean, `mypy --strict` clean on core paths, tests passing.
- **Every non-trivial decision:** appended to `DECISIONS.md` with date, decision, rationale, alternatives considered.

---

## How we work together

I'm solo, timeboxed, and relying on you heavily. Optimize for my throughput over your autonomy.

- **Vertical slice first, then replicate.** Day 1 builds one detector (`aws.encryption_s3_at_rest`) end-to-end through scan → evidence → provenance → CLI output. Days 2–4 replicate for five more, add agents, add polish. We do not build the whole framework before the first working detector.
- **Primitive-of-the-cycle rhythm.** We agree on the next primitive's contract in chat before you implement. You implement + test. I review. Move on.
- **Surface architectural questions immediately.** If you see a fork in the road, stop and ask. Do not silently pick and refactor later.
- **Prefer small PRs.** If a change touches more than three files outside of pure additions, flag it.
- **When stuck, say so.** If FRMR modeling, trestle behavior with the 800-53 catalog, or an MCP quirk is blocking you, surface it rather than working around it silently.
- **Maintain `DECISIONS.md`.** This is judge-facing and contributor-facing. Every non-obvious choice belongs there.
- **Regenerate `docs/primitives.md`** from decorator metadata after every primitive addition (`efterlev docs regenerate`).

---

## Demo target (the thing we optimize for)

The 4-day demo is this command sequence, end to end:

```bash
efterlev init --target ./demo/govnotes --baseline fedramp-20x-moderate
efterlev scan                              # produces evidence for KSIs (and 800-53 controls)
efterlev agent gap                         # classifies KSI status; HTML report
efterlev agent document                    # drafts FRMR-compatible attestation JSON + HTML
efterlev agent remediate --ksi KSI-SVC-VRI # proposes a Terraform diff fixing a gap
efterlev provenance show <record_id>
```

Plus: a second Claude Code session connecting to our MCP server and calling a primitive live. This is the architectural proof.

If a feature does not directly serve this flow or the architectural story behind it, defer it.

---

## Never do

- Never commit real secrets, API keys, or production data. The demo repo is synthetic.
- Never return FRMR (or, in v1, OSCAL) that hasn't been validated against its schema.
- Never generate a Claim without citing the Evidence records it derives from.
- Never claim the tool produces an ATO, a pass, or a guarantee of compliance. Drafts and findings only.
- Never add a dependency without a line in `DECISIONS.md` explaining why.
- Never expand the detection scope beyond the six areas above without explicit approval.
- Never mix Evidence and Claims in a way that loses their distinction — in the data model, in the UI, or in FRMR/OSCAL output.
- Never claim a detector proves more than it actually does. The "does NOT prove" section of the detector docstring is as important as the "does prove" section.
- Never invent a KSI ID that does not appear in the vendored FRMR. If coverage is genuinely missing, mark `[TBD]` and surface the gap; do not paper over it.

---

## References

- `docs/dual_horizon_plan.md` — full plan, including day-by-day schedule, demo script, and post-hackathon roadmap
- `docs/icp.md` — the Ideal Customer Profile; lens for every product decision
- `docs/scope.md` — the MVP contract
- `docs/architecture.md` — deeper architectural detail
- `docs/day1_brief.md` — quick-reference for Day 1 of the hackathon (design calls, vertical slice, guardrails)
- `DECISIONS.md` — running decision log
- `LIMITATIONS.md` — honest scope of what the tool does and doesn't do
- `THREAT_MODEL.md` — security posture for the tool itself
- `COMPETITIVE_LANDSCAPE.md` — positioning against Comp AI, RegScale OSCAL Hub, and others

When any of those conflict with this file, this file wins and we update the others.
