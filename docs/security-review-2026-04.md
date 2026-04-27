# Pre-launch security review — 2026-04

**Status:** evidence gathered 2026-04-26 (evidence pass); reviewer sign-off pending
**Reviewer:** _pending — to be filled in by maintainer at sign-off_
**Commit SHA:** `c2f3c88ecebcb458ff5236fee5ad4546303abb1c` (main, pre-flip; post-Phase-2 + post-dry-run)
**Repo state:** pre-launch (private), all A1–A8 readiness gates closed at the spec level; destination-repo operational setup applied; release pipeline validated via 5 rc-tag dry-runs

This document is the structured walkthrough required by SPEC-30.8 before the repo flips public. It records what the reviewer looked at, what they found, and what didn't make the cut. It is NOT a marketing artifact — failures land here truthfully.

The spot-check evidence below was gathered by running the verification suite at the SHA above (full results in §0). The maintainer fills in the sign-off line at §8 once they've eyeballed the evidence and agreed nothing in §7 is a launch blocker.

This review went through a critical-friend round on 2026-04-26 (in-session reviewer raised gaps in evidence coverage). The added rows in §0 — gitleaks against full git history, bandit + semgrep + CodeQL pass-rates, container-image CVE scan, license audit, SBOM generation — exist because of that pass.

---

## 0. Verification suite (at review SHA)

| Check | Command | Result |
|---|---|---|
| Unit + integration tests (no e2e) | `uv run --extra dev pytest -m "not e2e"` | 621 passed, 2 deselected (e2e) |
| Lint | `uv run --extra dev ruff check` | All checks passed |
| Format compliance | `uv run --extra dev ruff format --check` | 209 files already formatted |
| Type-check (strict on per-module overrides) | `uv run --extra dev mypy` | 129 source files clean |
| Docs site build | `uv run --extra docs mkdocs build --strict` | exit 0 |
| Doc-vs-code drift | `uv run python scripts/check-docs.py` | RESULT: clean |
| Pre-flip grep-scrub (current tree) | `bash scripts/launch-grep-scrub.sh` | RESULT: clean. Repo passes pre-flip grep-scrub. |
| Dogfood against pinned real-world Terraform | `bash scripts/dogfood-real-codebases.sh` | RESULT: all dogfood targets within thresholds (7 repos, 0 catastrophic regressions). |
| Dependency CVE scan (runtime) | `pip-audit -r <runtime deps via uv export --no-dev>` | No known vulnerabilities |
| Dependency CVE scan (runtime + dev) | `pip-audit -r <all deps via uv export>` | No known vulnerabilities |
| **Git history secret scan** | `gitleaks git --redact --config .gitleaks.toml` | 138 commits scanned, no leaks found (24 raw findings allowlisted by file-path; all are scrubber-test fixtures — see `.gitleaks.toml` for the rationale block). |
| **Bandit static security scan** (CI threshold) | `bandit -r src/efterlev --exclude tests --severity-level medium --confidence-level medium` | No issues identified at threshold. (12 low-severity hits below threshold; 1 medium-severity at low-confidence; threshold is medium∩medium.) |
| **Semgrep curated security rule set** | `semgrep --config p/python --config r/python.lang.security` (CI workflow `ci-security.yml::semgrep`) | success on the v0.0.1-rc.5 push run. |
| **CodeQL Python analysis** | `github/codeql-action/analyze@v3` (CI workflow `ci-security.yml::codeql`) | analysis completes; SARIF upload step soft-fails on private repo without GitHub Advanced Security (job has `continue-on-error: true`). The analysis itself runs cleanly across 209 Python files. Code Scanning gets enabled at flip-hour; the soft-fail is removed at the same time. |
| **Container OS-package CVE scan** | `trivy image --severity CRITICAL,HIGH ghcr.io/efterlev/efterlev:v0.0.1-rc.5` | 11 findings (2 CRITICAL, 9 HIGH); ALL inherited from the `python:3.12-slim-bookworm` base image (`ncurses-base`, `ncurses-bin`, `zlib1g`, `libssl3`, etc.). 1 marked `will_not_fix` upstream. Tracked + accepted at v0.1.0 — see §7. |
| **SBOM generation** (image) | `syft ghcr.io/efterlev/efterlev:v0.0.1-rc.5 -o cyclonedx-json` | 3,600 components emitted. Will be attached to the GitHub Release alongside the wheel/sdist post-launch (tracked in §7 + `docs/launch/post-launch-followups.md`). |
| **SBOM generation** (Python deps) | `syft dir:. -o cyclonedx-json --select-catalogers python` | 451 components emitted. |
| **License audit (Apache-2.0 compatibility)** | `pip-licenses --from=mixed --format=json` | 99 packages in the runtime venv; license distribution: 32 MIT, 20 MIT License, 10 BSD-3-Clause, 7 Apache Software License, 7 Apache-2.0, 4 BSD License, 3 BSD-2-Clause, 2 MPL-2.0, 2 ISC; 0 GPL/AGPL/SSPL/proprietary. **Apache-2.0-incompatible licenses: 0.** |
| **detectors-list command (T2 dep)** | `efterlev detectors list` | exists; emits 30 detectors with id@version, source, KSI mapping, control mapping. (Validated 2026-04-25 in PR #11; see §1 T2 row.) |

## 1. Threat-model coverage

For each named threat in [`THREAT_MODEL.md`](../THREAT_MODEL.md):

| Threat | Status | Spot-check evidence |
|---|---|---|
| **T1** — Sensitive source content exposed via LLM API | Mitigated | `scrub_llm_prompt` called unconditionally inside `format_evidence_for_prompt` (`src/efterlev/agents/base.py:133`) and `format_source_files_for_prompt` (`src/efterlev/agents/base.py:189`). Pattern library covers AWS keys, GCP keys, GitHub/Slack/Stripe tokens, PEM private keys, JWTs (`src/efterlev/llm/scrubber.py`). Fail-closed: scrubber exception aborts prompt assembly. Residual risk (custom token formats, high-entropy adjacent secrets) called out in THREAT_MODEL.md and LIMITATIONS.md. |
| **T2** — Compromised detector | Accepted residual risk (third-party detectors); mitigated for core | Core detectors live under `src/efterlev/detectors/aws/` and ship in the wheel; third-party detector packages are opt-in and explicitly listed by `efterlev detectors list` before any scan (verified — see §0 row "detectors-list command"). Same trust model as any Python dep. |
| **T3** — Hallucinated evidence accepted as real | Mitigated (defense-in-depth at two layers) | (a) Per-agent fence validators: `gap.py:211 _validate_cited_ids`, `documentation.py:263 _validate_cited_ids`, `remediation.py:206 _validate_citations` (different name, same contract — naming inconsistency tracked in §7). (b) Store-level: `ProvenanceStore.write_record` calls `_validate_claim_derived_from` for `record_type="claim"` records with non-empty `derived_from` BEFORE INSERT (`src/efterlev/provenance/store.py:130`). Atomicity: insert happens under `_write_lock` after the check; rejected claim never mutates the store. Tests in `tests/test_validate_claim_provenance.py` exercise both record-id and evidence-id resolution + insertion-atomicity. |
| **T4** — Provenance store tampering | Mitigated (detective, not preventive) | Content-addressed storage (SHA-256 canonical-bytes); modification changes the ID. `efterlev provenance verify` walks every record, recomputes the blob's SHA-256, compares to the embedded path-hash, lists mismatches. Test coverage: `tests/test_cli.py::test_provenance_verify_clean_store_passes` + `::test_provenance_verify_detects_tampered_blob`. Non-mitigation called out: Efterlev does not sign its own provenance store — that's the user's responsibility (cosign, Git commit signing, etc.). |
| **T5** — Supply chain compromise of Efterlev itself | Mitigated via release pipeline (signed wheels, container images, SLSA provenance); see §5 | Sigstore keyless-OIDC for both PyPI publish (trusted publishing, `release-pypi.yml`) and container signing (`cosign sign`, `release-container.yml`). Catalogs SHA-256-pinned at load (`src/efterlev/paths.py::verify_catalog_hashes`). Validated end-to-end via 5 rc-tag dry-runs (DECISIONS 2026-04-26). |
| **T6** — MCP attack surface | Mitigated (stdio-only, subprocess-parent trust) | v0 server speaks MCP over stdio only — never TCP. Per DECISIONS 2026-04-21 design call #4. Tool-call audit log writes one ProvenanceRecord per invocation. API key stays server-side. **Path-argument confused-deputy:** the MCP server accepts `target` paths from the client. The blast radius is bounded — the server requires `.efterlev/` to exist under the target and reads `.tf` files relative to that root, so an attacker who can spawn the server can only touch repos that already have the workspace structure. The same attacker has shell-equivalent access (they spawned the subprocess), so the path-argument doesn't expand their capabilities. Worth naming explicitly. |
| **T7** — Public-repo source review for prompt-injection paths | Mitigated (per-run nonces) + responsive process | Per-run-nonced XML fences (`new_fence_nonce` in `agents/base.py`) — the algorithm is publishable, the per-run nonce is generated at agent invocation. Conservative scrubber patterns. SECURITY.md disclosure path turns reported bypasses into test fixtures. |
| **T8** — Malicious PR (backdoor in detector or agent prompt) | Mitigated by branch protection + CI security scans | Branch ruleset id `15566618` on `main` (Active, no admin bypass) requires signed commits + linear history + 5 required status checks: `lint, type-check, test`, `DCO`, `pip-audit`, `bandit`, `semgrep`. CI security scans run on every PR — see §0 rows for results. CODEOWNERS gates reviewers. |
| **T9** — Dependency poisoning | Mitigated (pinned + audited + auto-updated) | `pyproject.toml` pins majors with explicit upper bounds. `.github/dependabot.yml` covers pip + github-actions + docker (weekly). `pip-audit` in CI security workflow. License audit (§0 row) confirms no GPL/AGPL/SSPL contamination. Container images bake deps at build then sign the immutable artifact. |
| **T10** — Release-artifact tampering | Mitigated (Sigstore + SLSA) | Sigstore keyless-OIDC binds artifact ↔ workflow ↔ commit SHA. SLSA provenance attestations via `docker/build-push-action@v6 provenance: mode=max`. `scripts/verify-release.sh` runs all three checks (signature, SLSA, content hash). `docs/RELEASE.md` template documents user-side verification. Tags `v0.0.1-rc.[1-5]` on TestPyPI persist as iteration evidence anyone can audit. |

## 2. Dependency review

### CVE scan

`pip-audit` (runtime deps only):

```
$ uv export --no-dev --format requirements-txt --no-emit-project | pip-audit -r /dev/stdin
No known vulnerabilities found
```

`pip-audit` (runtime + dev deps):

```
$ uv export --format requirements-txt --no-emit-project | pip-audit -r /dev/stdin
No known vulnerabilities found
```

### Static analysis (Python source)

| Tool | Threshold | Result |
|---|---|---|
| Bandit | severity ≥ medium AND confidence ≥ medium | No issues identified |
| Semgrep | curated `p/python` + `r/python.lang.security` rule sets | success on the v0.0.1-rc.5 push run; CI workflow `ci-security.yml::semgrep` clean across 5 dry-run rounds |
| CodeQL | `security-and-quality` query suite | analysis completes (209 Python files, 9 GitHub Actions files); SARIF upload soft-fails on private repo without GitHub Advanced Security; the soft-fail is `continue-on-error: true` (removed at flip-hour when Code Scanning is enabled) |

### Container OS-package CVE scan

`trivy image --severity CRITICAL,HIGH ghcr.io/efterlev/efterlev:v0.0.1-rc.5`:

| Severity | Count | Status |
|---|---|---|
| CRITICAL | 2 | inherited from `python:3.12-slim-bookworm` base image |
| HIGH | 9 | inherited from base image |
| Total | 11 | 1 marked `will_not_fix` upstream by Debian |

**Acceptance posture:** all 11 findings are inherited from the Debian base layer (ncurses, zlib1g, libssl3, etc.). Efterlev itself does not directly use the affected libraries in user-facing ways — Efterlev is a CLI processing IaC files, not a network-facing service that would expose these libraries to arbitrary input. Acceptance rationale: the base image is `python:3.12-slim-bookworm`, a Python Foundation-maintained image; we rebuild on every Dependabot bump (weekly cadence) so fixes propagate as Debian publishes them. Dependabot's docker ecosystem watches the base image. Tracked in §7 with the v0.2.0 alternative-base-image follow-up.

### SBOM

| Artifact | Tool | Component count |
|---|---|---|
| Container image | `syft ghcr.io/efterlev/efterlev:v0.0.1-rc.5 -o cyclonedx-json` | 3,600 |
| Python dependency tree (project) | `syft dir:. -o cyclonedx-json --select-catalogers python` | 451 |

CycloneDX format. To be attached to the GitHub Release at v0.1.0 launch (tracked in §7 + `docs/launch/post-launch-followups.md`).

### License compatibility (Apache-2.0)

`pip-licenses --from=mixed --format=json` against the runtime venv:

| License (top families) | Count |
|---|---|
| MIT / MIT License | 52 |
| BSD-3-Clause / BSD License / BSD-2-Clause | 17 |
| Apache-2.0 / Apache Software License / Apache License 2.0 | 15 |
| Mozilla Public License 2.0 | 2 |
| ISC | 2 |
| Other (PSF, Public Domain, Unlicense, ...) | 11 |

**GPL / AGPL / SSPL / proprietary count: 0.** Net: every runtime dependency is compatible with redistribution under Apache 2.0.

### Waived findings

| CVE | Package | Why waived |
|---|---|---|
| _none — no in-Python-dep CVEs at this SHA._ | | |

(Container OS-package CVEs are listed above with their acceptance rationale, not waived per se — they're the upstream base image, monitored via Dependabot.)

### Notes for the reviewer

`pip-audit`, `bandit`, `semgrep`, `gitleaks`, `trivy`, `syft`, `pip-licenses` are not installed by default in the dev venv — they're invoked via `uvx` (one-shot tool install) or via `brew install` for the binary tools (`gitleaks`, `trivy`, `syft`). The CI workflows (`ci-security.yml`) install them inline. Open question for v0.2.0: bake `pip-audit` and `bandit` into the dev extra to keep local-dev parity with CI.

## 3. Secret-handling review

`scrub_llm_prompt` confirmed unconditional on all egress paths. Spot-check at three named code paths:

- [x] **`format_evidence_for_prompt`** — `src/efterlev/agents/base.py:80`. Calls `scrub_llm_prompt(...)` at line 133 before any fence wrapping. Scrubber exception propagates (fail-closed).
- [x] **`format_source_files_for_prompt`** — `src/efterlev/agents/base.py:157`. Calls `scrub_llm_prompt(...)` at line 189. Same fail-closed contract.
- [x] **`AnthropicBedrockClient.complete` (SPEC-10)** — `src/efterlev/llm/bedrock_client.py`. Confirmed by tracing one call: prompts arrive at `bedrock_client.complete(...)` already scrubbed (the scrubber runs upstream in `format_*_for_prompt` inside the agents, not in the client). The Bedrock client doesn't itself transmit user content — it only forwards the already-formatted prompt strings. No bypass surface introduced.

**Fail-closed property is test-covered:** `tests/test_scrubber.py` exercises the scrubber under fault injection (test names include `test_scrubber_failure_aborts_prompt`-shape). All scrubber tests green at the review SHA.

**Audit trail:** the `RedactionLedger` writes to `.efterlev/redacted.log` at end-of-scan with `{timestamp, pattern_name, sha256_prefix, context_hint}` — never the secret value. 8-hex-char prefix has enough entropy to distinguish redactions within a scan, not enough for preimage recovery.

**No bypass paths identified.**

## 4. Provenance integrity review

`validate_claim_provenance` confirmed wired at the store-write boundary:

- [x] **`src/efterlev/provenance/store.py:130`** — `write_record` calls `self._validate_claim_derived_from(derived_from)` for `record_type="claim"` records with non-empty `derived_from`, BEFORE `INSERT`. Mismatched citation raises `ProvenanceError`; the record never reaches the `INSERT` statement (which then runs under `_write_lock`).
- [x] **`tests/test_validate_claim_provenance.py`** — exercises both resolution paths (`record_id` and `evidence_id`) AND insertion-atomicity (rejected claim does not mutate the store; subsequent reads see the pre-attempt state). 11 test functions, all green.
- [x] **Per-agent `_validate_cited_ids` helpers** — confirmed for all three generative agents. Each rejects model-output citing IDs that didn't appear inside a per-run-nonced fence in the prompt.
  - `src/efterlev/agents/gap.py:211` — `_validate_cited_ids`
  - `src/efterlev/agents/documentation.py:263` — `_validate_cited_ids`
  - `src/efterlev/agents/remediation.py:206` — `_validate_citations` (same contract, different name; cosmetic; tracked in §7)

Defense-in-depth: per-agent fence validators are the primary enforcement (catches the "model hallucinated an id" case at the agent boundary); the store-level check is the secondary enforcement (catches buggy-agent-code or any direct-store-write paths).

**Walker dual-key fix (2026-04-25):** the 3PAO acting review surfaced that cited `evidence_id`s didn't resolve via `efterlev provenance show` because the walker did single-key lookup against `record_id` while the validator did dual-key. Fixed in commit `54e8b47`: `ProvenanceStore.resolve_to_record(citation_id)` does the same dual-key lookup, walker uses it. Test coverage in `tests/test_provenance.py::test_walker_resolves_evidence_id_via_dual_key_lookup`.

## 5. Build + release review

Each release pipeline uses keyless OIDC auth and Sigstore signing — no long-lived credentials.

- [x] **`.github/workflows/release-pypi.yml`** — uses `pypa/gh-action-pypi-publish@release/v1` (TestPyPI smoke first then real PyPI) with trusted publishing (no API token). The `pypi` GitHub environment carries a deployment-tag-pattern restriction (`v[0-9]*.[0-9]*.[0-9]*`) that blocks any non-final-semver tag from triggering real-PyPI publish. Required-reviewer is plan-gated on Free/Pro plans for private repos; the destination repo is on GitHub Team which unlocks it — required-reviewer can be added at flip-hour or kept as the tag-pattern-only gate. Validated end-to-end via 5 rc-tag dry-runs (DECISIONS 2026-04-26).
- [x] **`.github/workflows/release-container.yml`** — `id-token: write` permission; `sigstore/cosign-installer@v3`; `cosign sign --yes "${IMAGE}@${DIGEST}"` (signs by digest not tag — cosign-recommended); `cosign verify` post-push to confirm the signature on what's actually in the registry. SLSA provenance via `docker/build-push-action@v6 provenance: mode=max`. SBOM emission via buildx `sbom: true`. Validated end-to-end 5 dry-run rounds.
- [x] **`.github/workflows/release-smoke.yml`** — runs install-verification matrix in parallel with the release jobs. Configured non-blocking (`continue-on-error: true` on the matrix job) at v0.1.0 — see DECISIONS 2026-04-26 "Pipeline dry-run" for the rationale and `docs/launch/post-launch-followups.md` for the v0.1.x re-blocking plan. ghcr.io cells cover Linux x86 + arm64; pipx cells cover Linux + macOS + Windows.
- [x] **No long-lived secrets in any release workflow.** GitHub Container Registry (ghcr.io) uses the per-job `GITHUB_TOKEN` (ephemeral). PyPI and TestPyPI use Trusted Publishing (no token required). Docker Hub publish was originally a parallel target requiring a `DOCKERHUB_TOKEN`, but was dropped at v0.1.0 after Docker Hub eliminated the free organization tier. Net effect: the v0.1.0 release pipeline has zero long-lived credentials — every signing and publish operation runs under the GitHub Actions workflow's OIDC identity.

**SLSA provenance.** Build-and-push action emits SLSA Level 3 provenance attestations bound to the workflow identity. Verified at the registry layer by `cosign verify-attestation` in `scripts/verify-release.sh`. Users running this script post-release confirm not just signature but also the build was produced by the expected workflow on the expected commit.

**SBOM publication path.** `release-container.yml` already passes `sbom: true` to buildx, which embeds an SBOM in the registry. The wheel doesn't currently get a separate SBOM attached to the GitHub Release; that's tracked as a v0.1.x enhancement (see §7) — at v0.1.0 the registry-side SBOM is sufficient for the launch-day claim.

**GitHub Actions pinning.** This document references actions by floating tag (`@v3`, `@release/v1`, `@v6`), not commit SHA. OpenSSF Scorecard and SLSA L3 expectation is to pin third-party actions to commit SHAs (`uses: org/action@<full-sha> # v3.4.0`). Acceptance posture for v0.1.0: vendor-maintained actions from `pypa`, `sigstore`, `docker`, `actions`, `astral-sh`, `github` are accepted at floating tag with the rationale that breaking changes from these vendors are caught by the Dependabot github-actions ecosystem (which we do have configured). Tracked as a v0.2.0 hardening item — pinning + auto-Dependabot-update-PRs is the right combination, and we want to land the dependabot-grouping fix first so a SHA-pinning sweep doesn't open 20 PRs at once.

## 6. Public-repo posture

- [x] **No accidental NDA-era / private-repo-era language remaining.** `bash scripts/launch-grep-scrub.sh` exits 0 (`RESULT: clean. Repo passes pre-flip grep-scrub.`). All allowlist entries carry rationale comments.
- [x] **No internal hostnames, SSH keys, or credentials in any committed file.** Two layers of evidence:
  - **Current tree:** the four secret-shape patterns in the grep-scrub catch zero matches.
  - **Full git history:** `gitleaks git --redact --config .gitleaks.toml` scans 138 commits and reports no leaks. Raw scan (without allowlist) finds 24 hits, ALL in `tests/test_scrubber.py`, `tests/test_redaction_integration.py`, and `scripts/e2e_smoke.py` — synthetic secret-shaped strings used to TEST the scrubber library. The `.gitleaks.toml` allowlist explicitly permits these test files with rationale.
- [x] **`.gitignore` and `.dockerignore` confirmed correct.**
  - `.gitignore`: `.efterlev/*` excluded with `!.efterlev/manifests/` un-ignored (customer-authored procedural attestations are version-controlled alongside the code they describe — by design); `out/`, `dist/`, `site/`, `.venv/`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.coverage` all excluded.
  - `.dockerignore`: `.efterlev`, `.e2e-results`, `tests/`, `scripts/`, `docs/`, `.github/`, `.git`, dev caches, fixtures all excluded — wheel is self-contained at runtime.
- [x] **Branch protection on `main` configured per `.github/BRANCH_PROTECTION.md`.** Applied 2026-04-26 as GitHub Ruleset id `15566618` on `efterlev/efterlev` (lowercase, post-rename). Active enforcement, empty bypass list (no admin override), 5 required status checks (`lint, type-check, test`, `DCO`, `pip-audit (Python deps)`, `bandit (Python static security analysis)`, `semgrep (security rule set)`), required signed commits + linear history. Validated end-to-end via PRs #12, #15-#21 — every PR required signed commits and the full required-check set to pass before squash-merge. (Note: applied via GitHub's newer Rulesets UI, not the older "Branch protection rules" UI; semantics are identical, surface area is broader.)
- [x] **Org transfer.** Repo transferred from `lhassa8/Efterlev` → `efterlev/efterlev` on 2026-04-26. GitHub auto-redirects the old URL to the new path (still active — `git ls-remote https://github.com/lhassa8/Efterlev.git` resolves). No third-party CI integrations to re-authorize (the only third-party integration is the DCO GitHub App, which was installed on the new org post-transfer). Pre-rename PR/issue references in docs are tolerated by the redirect; new internal references use `efterlev/efterlev` (verified via grep-scrub).

## 7. Open items

Items found during review that didn't make the launch cut. Each item is tracked in `docs/launch/post-launch-followups.md` for v0.1.x or v0.2.0+. None are launch blockers.

| Issue | Severity | Why not a blocker | Tracking |
|---|---|---|---|
| Container base image inherits 11 OS-package CVEs from `python:3.12-slim-bookworm` (2 CRITICAL, 9 HIGH, 1 `will_not_fix` upstream) | medium | All inherited from Debian; not directly exposed by Efterlev's CLI usage; Dependabot rebuilds weekly so fixes propagate as Debian publishes them. v0.2.0 follow-up: evaluate distroless or chainguard-style minimal base. | post-launch-followups.md (new entry to add) |
| GitHub Actions referenced by floating tag, not commit SHA | medium | All actions are vendor-maintained (`pypa`, `sigstore`, `docker`, `actions`, `astral-sh`); breaking changes are caught by Dependabot's github-actions ecosystem. SHA-pinning is a v0.2.0 hardening item; want the dependabot-grouping fix first so the SHA sweep doesn't open 20 PRs at once. | post-launch-followups.md (new entry to add) |
| SBOM not attached to the GitHub Release at v0.1.0 | low | Container image already carries embedded SBOM via `buildx sbom: true`. Wheel-level SBOM attachment is a v0.1.x enhancement; the registry-side SBOM is sufficient for the launch-day "we ship an SBOM" claim. | post-launch-followups.md (new entry to add) |
| `_validate_citations` (remediation) vs `_validate_cited_ids` (gap, documentation) naming inconsistency | trivial | Same contract, just different names. Cosmetic. v0.2.0 follow-up: rename to one canonical form. | post-launch-followups.md (existing — narrative-template + naming cleanup) |
| Bake `pip-audit` and `bandit` into the `[dev]` extra | low | The CI workflow runs the same scan; local-dev parity is nice-to-have. v0.2.0 follow-up. | post-launch-followups.md (new entry to add) |
| `pypi` env required-reviewer not configured | low | Tag-pattern restriction (`v[0-9]*.[0-9]*.[0-9]*`) on the `pypi` env provides a coarser gate. Required-reviewer can be added at flip-hour or kept off; either is defensible. | post-launch-followups.md (existing — Re-add `pypi` environment required reviewer) |
| `release-smoke.yml` matrix non-blocking at v0.1.0 | low | Pipeline-critical paths validated; smoke matrix surfaces install-time issues fighting CI infrastructure rather than product bugs. Re-blocking is v0.1.x work. | post-launch-followups.md (existing — Smoke matrix re-blocking) |
| `macos-13 / pipx` smoke cell stuck queued in 5/5 dry-run rounds | low | Cell removal bundled with the smoke re-blocking work. | post-launch-followups.md (existing) |

## 8. Sign-off

| Reviewer | GitHub handle | Commit SHA reviewed | Date | Notes |
|---|---|---|---|---|
| _Pending — maintainer self-review per BDFL-era process_ | _e.g., `@lhassa8`_ | `c2f3c88ecebcb458ff5236fee5ad4546303abb1c` | _YYYY-MM-DD_ | _e.g., "Eyeballed evidence rows in §0; agreed §7 items are tracked and non-blocking; ran each §0 command myself rather than just trusting the documented result. Signed off."_ |

A second reviewer is welcome but not required at v0.1.0 — the BDFL-era process is a self-review with the rigor this template enforces. A second reviewer is recommended for v0.2.0 onward as the contributor pool grows.

**Template-followed meta-check.** This review is structurally a self-attestation: the maintainer documents what they ran and what they found. To prevent template drift over releases, the v0.2.0 review (and beyond) should include one row in §8 attesting that the §0 commands were actually executed for that release's SHA — the natural read otherwise is "the maintainer copy-pasted the previous review's results." For v0.1.0 the §0 commands ARE re-run on the actual review SHA (post-Phase-2, post-dry-run); each row's "Result" column reflects that run. Future releases follow the same discipline.
