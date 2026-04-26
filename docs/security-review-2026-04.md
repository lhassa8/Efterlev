# Pre-launch security review — 2026-04

**Status:** evidence gathered 2026-04-25; reviewer sign-off pending
**Reviewer:** _pending — to be filled in by maintainer at sign-off_
**Commit SHA:** `87a20040b022557aa316a199c632aa7d07fdecb4` (main, pre-flip)
**Repo state:** pre-launch (private), all A1–A8 readiness gates closed at the spec level

This document is the structured walkthrough required by SPEC-30.8 before the repo flips public. It records what the reviewer looked at, what they found, and what didn't make the cut. It is NOT a marketing artifact — failures land here truthfully.

The spot-check evidence below was gathered by running the verification suite at the SHA above (full results in §0). The maintainer fills in the sign-off line at §8 once they've eyeballed the evidence and agreed nothing in §7 is a launch blocker.

---

## 0. Verification suite (at review SHA)

| Check | Command | Result |
|---|---|---|
| Unit + integration tests (no e2e) | `uv run --extra dev pytest -m "not e2e"` | 602 passed, 2 deselected (e2e) |
| Lint | `uv run --extra dev ruff check` | All checks passed |
| Type-check (strict on per-module overrides) | `uv run --extra dev mypy` | 129 source files clean |
| Docs site build | `uv run --extra docs mkdocs build --strict` | exit 0 |
| Pre-flip grep-scrub | `bash scripts/launch-grep-scrub.sh` | RESULT: clean |
| Dependency CVE scan (runtime) | `pip-audit -r <runtime deps>` | No known vulnerabilities |
| Dependency CVE scan (runtime + dev) | `pip-audit -r <all deps>` | No known vulnerabilities |

## 1. Threat-model coverage

For each named threat in [`THREAT_MODEL.md`](../THREAT_MODEL.md):

| Threat | Status | Spot-check evidence |
|---|---|---|
| **T1** — Sensitive source content exposed via LLM API | Mitigated | `scrub_llm_prompt` called unconditionally inside `format_evidence_for_prompt` (`src/efterlev/agents/base.py:133`) and `format_source_files_for_prompt` (`src/efterlev/agents/base.py:189`). Pattern library covers AWS keys, GCP keys, GitHub/Slack/Stripe tokens, PEM private keys, JWTs (`src/efterlev/llm/scrubber.py`). Fail-closed: scrubber exception aborts prompt assembly. Residual risk (custom token formats, high-entropy adjacent secrets) called out in THREAT_MODEL.md and LIMITATIONS.md. |
| **T2** — Compromised detector | Accepted residual risk (third-party detectors); mitigated for core | Core detectors live under `src/efterlev/detectors/aws/` and ship in the wheel; third-party detector packages are opt-in and explicitly listed by `efterlev detectors list` before any scan. Same trust model as any Python dep. |
| **T3** — Hallucinated evidence accepted as real | Mitigated (defense-in-depth at two layers) | (a) Per-agent fence validators: `gap.py:211 _validate_cited_ids`, `documentation.py:263 _validate_cited_ids`, `remediation.py:206 _validate_citations`. (b) Store-level: `ProvenanceStore.write_record` calls `_validate_claim_derived_from` for `record_type="claim"` records with non-empty `derived_from` BEFORE INSERT (`src/efterlev/provenance/store.py:130`). Atomicity: insert happens under `_write_lock` after the check; rejected claim never mutates the store. Tests in `tests/test_validate_claim_provenance.py` exercise both record-id and evidence-id resolution + insertion-atomicity. **Naming nit:** the original template said all three agents use `_validate_cited_ids`; remediation actually uses `_validate_citations` (same contract, different name) — corrected here, the implementation is sound. |
| **T4** — Provenance store tampering | Mitigated (detective, not preventive) | Content-addressed storage (SHA-256 canonical-bytes); modification changes the ID. `efterlev provenance verify` detects mismatches. Non-mitigation called out: Efterlev does not sign its own output — that's the user's responsibility (cosign, Git commit signing, etc.). |
| **T5** — Supply chain compromise of Efterlev itself | Mitigated via release pipeline (signed wheels, container images, SLSA provenance); see §5 | Sigstore keyless-OIDC for both PyPI publish (trusted publishing, `release-pypi.yml`) and container signing (`cosign sign`, `release-container.yml`). Catalogs SHA-256-pinned at load (`src/efterlev/paths.py::verify_catalog_hashes`). |
| **T6** — MCP attack surface | Mitigated (stdio-only, subprocess-parent trust) | v0 server speaks MCP over stdio only — never TCP. Per DECISIONS 2026-04-21 design call #4. Tool-call audit log writes one ProvenanceRecord per invocation. API key stays server-side. |
| **T7** — Public-repo source review for prompt-injection paths | Mitigated (per-run nonces) + responsive process | Per-run-nonced XML fences (`new_fence_nonce` in `agents/base.py`) — the algorithm is publishable, the per-run nonce is generated at agent invocation. Conservative scrubber patterns. SECURITY.md disclosure path turns reported bypasses into test fixtures. |
| **T8** — Malicious PR (backdoor in detector or agent prompt) | Mitigated by branch protection + CI security scans; depends on maintainer-action queue (see §6) | `.github/BRANCH_PROTECTION.md` documents the required configuration. CI security workflow `.github/workflows/ci-security.yml` runs pip-audit + bandit + semgrep + CodeQL. CODEOWNERS gates reviewers. **Open dependency:** branch protection must be applied via the GitHub UI before public flip. |
| **T9** — Dependency poisoning | Mitigated (pinned + audited + auto-updated) | `pyproject.toml` pins majors with explicit upper bounds. `.github/dependabot.yml` covers pip + github-actions + docker (weekly). `pip-audit` in CI security workflow. Container images bake deps at build then sign the immutable artifact. |
| **T10** — Release-artifact tampering | Mitigated (Sigstore + SLSA) | Sigstore keyless-OIDC binds artifact ↔ workflow ↔ commit SHA. SLSA provenance attestations. `scripts/verify-release.sh` runs all three checks. `docs/RELEASE.md` template documents user-side verification. |

## 2. Dependency review

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

**Waived findings:**

| CVE | Package | Why waived |
|---|---|---|
| _none_ | | |

**Notes for the reviewer:** `pip-audit` is currently invoked via `uvx --from pip-audit pip-audit` (one-shot tool install) rather than included in the `[dev]` extra. The `ci-security.yml` workflow runs the same scan in CI, so adding it to dev extras isn't strictly necessary. Open question for v0.2.0: bake `pip-audit` into the dev extra to keep local-dev parity with CI. Not a launch blocker.

## 3. Secret-handling review

`scrub_llm_prompt` confirmed unconditional on all egress paths. Spot-check at three named code paths:

- [x] **`format_evidence_for_prompt`** — `src/efterlev/agents/base.py:80`. Calls `scrub_llm_prompt(...)` at line 133 before any fence wrapping. Scrubber exception propagates (fail-closed).
- [x] **`format_source_files_for_prompt`** — `src/efterlev/agents/base.py:157`. Calls `scrub_llm_prompt(...)` at line 189. Same fail-closed contract.
- [x] **`AnthropicBedrockClient.complete` (SPEC-10)** — `src/efterlev/llm/bedrock_client.py`. Confirmed by tracing one call: prompts arrive at `bedrock_client.complete(...)` already scrubbed (the scrubber runs upstream in `format_*_for_prompt` inside the agents, not in the client). The Bedrock client doesn't itself transmit user content — it only forwards the already-formatted prompt strings. No bypass surface introduced.

**No bypass paths identified.**

Audit-trail: the `RedactionLedger` writes to `.efterlev/redacted.log` at end-of-scan with `{timestamp, pattern_name, sha256_prefix, context_hint}` — never the secret value. 8-hex-char prefix has enough entropy to distinguish redactions within a scan, not enough for preimage recovery.

## 4. Provenance integrity review

`validate_claim_provenance` confirmed wired at the store-write boundary:

- [x] **`src/efterlev/provenance/store.py:130`** — `write_record` calls `self._validate_claim_derived_from(derived_from)` for `record_type="claim"` records with non-empty `derived_from`, BEFORE `INSERT`. Mismatched citation raises `ProvenanceError`; the record never reaches the `INSERT` statement (which then runs under `_write_lock`).
- [x] **`tests/test_validate_claim_provenance.py`** — exercises both resolution paths (`record_id` and `evidence_id`) AND insertion-atomicity (rejected claim does not mutate the store; subsequent reads see the pre-attempt state). 11 test functions, all green.
- [x] **Per-agent `_validate_cited_ids` helpers** — confirmed for all three generative agents. Each rejects model-output citing IDs that didn't appear inside a per-run-nonced fence in the prompt.
  - `src/efterlev/agents/gap.py:211` — `_validate_cited_ids`
  - `src/efterlev/agents/documentation.py:263` — `_validate_cited_ids`
  - `src/efterlev/agents/remediation.py:206` — `_validate_citations` (different name, same contract — see T3 row above)

Defense-in-depth: per-agent fence validators are the primary enforcement (catches the "model hallucinated an id" case at the agent boundary); the store-level check is the secondary enforcement (catches buggy-agent-code or any direct-store-write paths).

## 5. Build + release review

Each release pipeline uses keyless OIDC auth and Sigstore signing — no long-lived credentials except where the upstream platform doesn't yet support keyless.

- [x] **`.github/workflows/release-pypi.yml`** — uses `pypa/gh-action-pypi-publish@release/v1` (lines 106 + 133, TestPyPI smoke first then real PyPI) with trusted publishing (no API token). The `pypi` GitHub environment requires manual approval on real-PyPI publish.
- [x] **`.github/workflows/release-container.yml`** — `id-token: write` permission (line 29); `sigstore/cosign-installer@v3` (line 109); `cosign sign --yes "${IMAGE}@${DIGEST}"` (line 128, signs by digest not tag — cosign-recommended); `cosign verify` post-push to confirm the signature on what's actually in the registry. SLSA provenance via buildx attestations.
- [x] **`.github/workflows/release-smoke.yml`** — runs install-verification matrix in parallel with the release jobs. Real-PyPI upload waits on the `pypi` environment's manual approval, which absorbs the natural lag between tag-push triggering release-pypi.yml and TestPyPI propagation.
- [x] **No long-lived secrets in any release workflow.** GitHub Container Registry (ghcr.io) uses the per-job `GITHUB_TOKEN` (ephemeral). PyPI and TestPyPI use Trusted Publishing (no token required). Docker Hub publish was originally a parallel target requiring a `DOCKERHUB_TOKEN`, but was dropped at v0.1.0 after Docker Hub eliminated the free organization tier (2026-04-26 update). Net effect: the v0.1.0 release pipeline has zero long-lived credentials — every signing and publish operation runs under the GitHub Actions workflow's OIDC identity.

## 6. Public-repo posture

- [x] **No accidental NDA-era / private-repo-era language remaining.** `bash scripts/launch-grep-scrub.sh` exits 0 (`RESULT: clean. Repo passes pre-flip grep-scrub.`). All allowlist entries carry rationale comments. The grep-scrub itself catches the legitimate-vocabulary cases (CIA-triad "confidentiality", FRMR mapping language, vendored NIST 800-53 catalog prose) and explicitly allowlists them.
- [x] **No internal hostnames, SSH keys, or credentials in any committed file.** Covered by the four secret-shape patterns in the grep-scrub (AWS access keys, Anthropic keys, GitHub tokens, PEM private keys); zero matches.
- [x] **`.gitignore` and `.dockerignore` confirmed correct.**
  - `.gitignore`: `.efterlev/*` excluded with `!.efterlev/manifests/` un-ignored (customer-authored procedural attestations are version-controlled alongside the code they describe — by design); `out/`, `dist/`, `.venv/`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.coverage` all excluded.
  - `.dockerignore`: `.efterlev`, `.e2e-results`, `tests/`, `scripts/`, `docs/`, `.github/`, `.git`, dev caches, fixtures all excluded — wheel is self-contained at runtime.
- [ ] **Branch protection on `main` configured per `.github/BRANCH_PROTECTION.md`.** **Not yet applied** — this is a maintainer-action item that runs through the GitHub UI on the destination repo (`efterlev/efterlev`) once the repo transfer from `lhassa8/Efterlev` lands. The configuration document is checked in; applying it is the maintainer's pre-flip task. **This is the only outstanding §6 item before public flip.**

## 7. Open items

- _Anything found during review that didn't make the launch cut. Each item gets a tracking issue once the public repo exists._

| Issue | Severity | Why not a blocker |
|---|---|---|
| Bake `pip-audit` into the `[dev]` extra | low | The CI workflow runs the same scan; local-dev parity is nice-to-have. v0.2.0 follow-up. |
| `_validate_citations` (remediation) vs `_validate_cited_ids` (gap, documentation) naming inconsistency | trivial | Same contract, just different names. Cosmetic. v0.2.0 follow-up: rename to one canonical form. |
| Branch protection on the destination repo | maintainer-action (must complete before public flip) | Documented in `.github/BRANCH_PROTECTION.md`; applied through GitHub UI post-transfer. Tracked in the maintainer-action queue, not the issue tracker. |

## 8. Sign-off

| Reviewer | GitHub handle | Commit SHA reviewed | Date | Notes |
|---|---|---|---|---|
| _Pending — maintainer self-review per BDFL-era process_ | _e.g., @lhassa8 → @efterlev-maintainer post-transfer_ | `87a20040b022557aa316a199c632aa7d07fdecb4` | _YYYY-MM-DD_ | _e.g., "Eyeballed evidence rows, agreed §7 items are non-blocking. Signed off."_ |

A second reviewer is welcome but not required at v0.1.0 — the BDFL-era process is a self-review with the rigor this template enforces. A second reviewer is recommended for v0.2.0 onward as the contributor pool grows.
