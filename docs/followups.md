# Follow-ups

Tracked work deferred from v0.1.0 to keep the launch surface tight. Items here are not launch blockers — they're real work scheduled for v0.1.x (patch follow-ups) or v0.2.0 (next minor).

Each entry names the deferral, the reason, the owner, and a target window. As items land, move them to the **Done** section at the bottom with their resolution.

---

## v0.1.x — patch-follow-ups (within first 30 days)

### Gap Agent / Remediate Agent disagree on KSI scope when Gap cites cross-thematic evidence

**Item:** the Gap Agent has freedom to cite any prompt-visible `Evidence` in a KSI's rationale, even Evidence whose `ksis_evidenced` doesn't include that KSI (e.g. citing FIPS-TLS evidence under KSI-AFR-UCM). When the user later runs `efterlev agent remediate --ksi <that-ksi>`, the CLI's gating logic strictly filters by `ev.ksis_evidenced`, finds zero Terraform-source Evidence, and refuses with `"no Terraform surface to remediate"`. The two agents disagree on what counts as "evidence for this KSI."

**Resolution path:** design call between two reasonable defaults:
1. **Trust Gap's citations** — replace remediate's `ksis_evidenced` filter with a lookup of the Claim's `derived_from` Evidence IDs (what Gap actually cited). Risk: amplifies any over-attachment by Gap into a remediation diff that addresses the wrong KSI.
2. **Enforce detector-level mapping** — keep remediate's strict filter and tighten Gap's prompt to forbid citing Evidence whose `ksis_evidenced` doesn't include the KSI. Risk: reduces Gap's ability to reason about thematically-adjacent evidence.

(2) is more defensive and matches the "honesty over polish" principle. Likely the right call but wants prompt iteration against a real-customer corpus.

**Owner:** Maintainer.

**Target:** v0.2.0 (wants real-customer corpus for prompt tuning).

**Cross-references:** v0.1.0 deep-dive shakedown report; not a regression — present in v0.1.0.

---

### Container base image — evaluate alternatives to `python:3.12-slim-bookworm`

**Item:** trivy scan of the v0.0.1-rc.5 image surfaced 11 CRITICAL/HIGH CVEs, all inherited from the `python:3.12-slim-bookworm` base layer (`ncurses-base`, `ncurses-bin`, `zlib1g`, etc.; one marked `will_not_fix` upstream by Debian). Efterlev's CLI usage doesn't directly expose these libraries to attacker input, but a leaner base image would shrink the inherited surface to near-zero.

**Resolution path:** evaluate alternatives in order of operational simplicity:
1. **Distroless** (`gcr.io/distroless/python3-debian12`) — smallest surface, no shell, no package manager. Trade-off: harder to debug interactively in production.
2. **Chainguard images** (`cgr.dev/chainguard/python`) — Wolfi-based, near-zero CVE rates, free for OSS. More involved to integrate but high-signal for security reviewers.
3. **Slim variants of newer Python releases** (`python:3.13-slim-bookworm` or `python:3.12-slim-trixie` when bookworm goes stable-2-cycles-old).

**Owner:** Maintainer.

**Target:** v0.2.0 if the alternative-base evaluation is straightforward; v0.3.0 if it requires Dockerfile refactoring.

**Cross-references:** `docs/security-review-2026-04.md` §7 row "Container base image inherits 11 OS-package CVEs."

---

### Pin third-party GitHub Actions to commit SHAs

**Item:** all release-pipeline workflows reference vendor actions by floating tag (`@v3`, `@release/v1`, `@v6`). OpenSSF Scorecard and SLSA L3 expectations call for SHA pinning.

**Resolution path:** sweep `.github/workflows/*.yml`, replace each `uses: org/action@<tag>` with `uses: org/action@<full-commit-sha> # <tag>`. Dependabot's github-actions ecosystem already opens PRs for action updates; with SHA pinning, those PRs become explicit-review-then-merge events instead of "trust the floating tag." Should land AFTER the dependabot-grouping fix (`patterns: ["*"]`) so the SHA sweep doesn't generate 20 separate update PRs.

**Owner:** Maintainer.

**Target:** v0.2.0.

**Cross-references:** `docs/security-review-2026-04.md` §5 + §7.

---

### Attach wheel-level SBOM to GitHub Releases

**Item:** the container image already carries an embedded SBOM via `buildx sbom: true`. The wheel/sdist published to PyPI doesn't currently get a separate SBOM file attached to the GitHub Release.

**Resolution path:** add a workflow step in `release-pypi.yml` (after the `build` job, before `publish-test-pypi`) that runs `syft dist/efterlev-<VERSION>-py3-none-any.whl -o cyclonedx-json > dist/efterlev-<VERSION>-sbom.cdx.json`, and uploads the SBOM file as a release asset alongside the wheel + sdist.

**Owner:** Maintainer.

**Target:** v0.1.x (small, self-contained, can land in any patch release).

**Cross-references:** `docs/security-review-2026-04.md` §5 + §7.

---

### Bake security tools into the `[dev]` extra

**Item:** `pip-audit`, `bandit` are invoked via `uvx` (one-shot tool install) rather than included in the `[dev]` extra. CI installs them inline. Local-dev parity with CI would be nicer.

**Resolution path:** add `pip-audit>=2.7,<3` and `bandit[toml]>=1.7,<2` to `[project.optional-dependencies].dev` in `pyproject.toml`. CI workflow can then `uv sync --extra dev` and call them directly.

**Owner:** Maintainer.

**Target:** v0.2.0.

**Cross-references:** `docs/security-review-2026-04.md` §7.

---

### Drop `macos-13 / pipx` cell from the smoke matrix

**Item:** the `macos-13` (x86 Intel Mac) cell got stuck queued for 90+ minutes in every round of the v0.0.1-rc.[1–5] dry-run — never got a runner. This is a GitHub-hosted x86 Mac runner capacity issue, chronic enough that the cell never produced signal in 5 attempts.

**Resolution path:** remove the `macos-13 / pipx` matrix entry from `release-smoke.yml`. macOS arm64 (`macos-14 / pipx`) covers all current and future Apple Silicon Macs; macOS Intel is increasingly minority hardware. If we want Intel Mac coverage later, fall back to letting the macOS arm64 cell run with Rosetta translation in CI rather than relying on the x86 GitHub-hosted runner pool.

**Owner:** Maintainer.

**Target:** v0.1.1 (bundle with the smoke-matrix re-blocking work below).

---

### Smoke matrix re-blocking

**Item:** `release-smoke.yml` is currently non-blocking (`continue-on-error: true` on the matrix job). Make it strictly required again.

**Why deferred:** during the v0.0.1-rc.[1–4] dry-runs (2026-04-26), the matrix surfaced four real workflow bugs (TestPyPI extra-index-url, uv prerelease policy, version-string shape, uv cache `--refresh`). Round 4 STILL failed despite all four fixes landing — the failure mode mutated to `setup-uv`'s cache-restore reading stale TestPyPI simple-index metadata in a way `--refresh` didn't fully bypass. Local install with identical uv version + flags worked first try. Conclusion: the matrix is fighting GitHub-CI infrastructure quirks, not product bugs.

**Resolution path:**
1. Watch the actual `release-smoke.yml` run on the real `v0.1.0` tag. If it surfaces real platform-specific install bugs, fix those first.
2. Likely fix: change the matrix's `setup-uv` step to `enable-cache: false`, OR set `UV_NO_CACHE=1` env var, OR add a longer initial wait before the first install attempt to give TestPyPI's CDN time to propagate. Test in isolation on a feature branch by tagging a test rc and watching only that workflow.
3. Once stable for two consecutive release tags, remove `continue-on-error: true`.

**Owner:** Maintainer.

**Target:** within 30 days post-launch; soft target for inclusion in v0.1.1 or v0.1.2.

**Cross-references:** `release-smoke.yml` job-level comment.

---

### Workflow comment fix on `release-pypi.yml`

**Item:** the workflow's leading comment used to say "Repository name: `efterlev`" (lowercase) when the repo was actually `efterlev/Efterlev` (capital E). Repo was renamed lowercase 2026-04-26 so the comment is now correct, BUT the case-sensitivity nuance isn't called out in the comment itself.

**Status:** partially-addressed in PR #12 (2026-04-26). Verify the wording is clear to a future maintainer reading the comment fresh.

**Owner:** Maintainer.

**Target:** when next touching the workflow.

---

### CodeQL upload re-enabled

**Item:** `ci-security.yml`'s CodeQL job has `continue-on-error: true` because the upload-to-Security-tab step 403s on private repos without GitHub Advanced Security.

**Resolution path** (post-launch — the repo is now public, so Advanced Security features unlock):
1. Enable Code Scanning (Settings → Code security and analysis).
2. Remove `continue-on-error: true` from the CodeQL job.

**Owner:** Maintainer.

**Target:** v0.1.x.

---

### Detector → KSI mapping coverage audit (SC-28 unmapped case)

**Item:** during the GovCloud-shaped walkthrough (2026-04-26), an `aws.encryption_s3_at_rest` finding (S3 bucket declared without `server_side_encryption_configuration`, controls=`SC-28`) was emitted by the detector and stored as evidence, but the Gap Agent classified it under "Unmapped findings" because no KSI in FRMR v0.9.43-beta directly claims SC-28. As a result, the POA&M emit did not surface the S3 finding under any `POAM-KSI-...` item — only under the unmapped block. A real customer scan with the same shape would produce a POA&M that visibly omits the S3 weakness from the KSI roll-up, even though the evidence was correctly captured.

**Reproduction:** initialize a directory with a Terraform `aws_s3_bucket` resource missing `server_side_encryption_configuration`, run `efterlev init && efterlev scan && efterlev agent gap && efterlev poam`. The S3 finding lands under "Unmapped findings (1)" in the gap-agent output.

**Resolution path:** two possible fixes, in order of likelihood:
1. **FRMR ruleset side** — verify whether SC-28 ("Protection of Information at Rest") is intended to map to KSI-SVC-RUD ("Removing Unwanted Data") or KSI-SVC-PRR ("Preventing Residual Risk"). SC-28 is squarely an encryption-at-rest control, so a KSI claim almost certainly should exist for it. If FRMR v0.9.43-beta is the canonical input and the mapping is genuinely absent, raise upstream rather than patching locally.
2. **Detector side** — if SC-28 has no clean KSI home in the current FRMR, the detector should explicitly populate `ksis_evidenced` with the closest-matching KSI (today the field is `[]` for this detector — see evidence record `3edd02ea...`), so the Gap Agent has a hook to attach the finding.

While investigating, audit all 30 detectors for the same shape (controls populated, `ksis_evidenced` empty, no FRMR-side bridge) — this likely isn't unique to S3 encryption.

**Owner:** Maintainer.

**Target:** v0.1.x — small, bounded investigation; likely a one-PR fix once the right side (FRMR vs. detector) is identified.

**Cross-references:** v0.0.1-rc.5 walkthrough, evidence record `sha256:dd1031394b...` (the S3 unencrypted finding); FRMR `cache/frmr_document.json` v0.9.43-beta.

---

### Re-add `pypi` environment required reviewer

**Item:** the `pypi` GitHub environment was configured with a deployment-tag-pattern restriction (`v[0-9]*.[0-9]*.[0-9]*`) but no required-reviewer because the GitHub-Team plan didn't expose required-reviewers on private repos.

**Status:** plan upgraded to GitHub Team mid-launch-prep, which DID unlock required-reviewers on private. The maintainer can add themselves as `pypi` env reviewer if desired. Currently NOT configured because we never got back to it after the upgrade.

**Owner:** Maintainer.

**Target:** before first real `v0.1.0` tag push (manual gate before real-PyPI publish).

---

### File upstream FRMR issue: SC-28 has no KSI mapping in 0.9.43-beta

**Item:** the 2026-04-27 Priority 6 honesty pass confirmed that SC-28 ("Protection of Information at Rest") is not in any FRMR 0.9.43-beta KSI's `controls` array, even though encryption-at-rest is one of the most fundamental confidentiality controls in any compliance posture. As a result, 5 of Efterlev's 30 detectors (`encryption_s3_at_rest`, `encryption_ebs`, `rds_encryption_at_rest`, `sqs_queue_encryption`, `sns_topic_encryption`) cannot map to any KSI and surface as "supplementary 800-53 evidence" only.

We considered KSI-SVC-VRI ("Validating Resource Integrity"), KSI-SVC-PRR ("Preventing Residual Risk"), and KSI-SVC-RUD ("Removing Unwanted Data") as candidate homes; all rejected as off-thematically (VRI's controls center on SC-13 integrity, PRR has only SC-4 — Information in Shared System Resources, RUD has SI-12.3 / SI-18.4 data integrity). The natural KSI for SC-28 would either be a new "Protecting Information at Rest" KSI in the SVC theme, or extension of an existing SVC KSI to include SC-28 in its controls.

**Resolution path:**
1. File an upstream issue at the FRMR repo (`FedRAMP/docs` or wherever FRMR is maintained) describing the gap with concrete evidence of dispositive IaC-level encryption-at-rest evidence Efterlev produces.
2. Propose a mapping (likely either: extend KSI-SVC-PRR to include SC-28, OR add a new KSI for "encryption at rest" specifically).
3. When FRMR ships a version with the mapping, bump the catalog and rehome the 5 detectors from `ksis=[]` to the new mapping.

**Owner:** Maintainer (file upstream); upstream FRMR maintainers (decide on resolution).

**Target:** v0.2.0 catalog bump if FRMR resolves; otherwise this stays open and the 5 detectors stay supplementary-only with documented rationale.

**Cross-references:** individual detector READMEs under `src/efterlev/detectors/aws/encryption_*/`, DECISIONS 2026-04-21 and 2026-04-27 honesty pass.

---

## v0.2.0+ — minor-release follow-ups

### Dedupe unmapped findings (and possibly all evidence) across re-scans

**Item:** `Evidence` content includes `timestamp`, so the SHA-256 `evidence_id` is fresh on every scan. The provenance store is append-only, so re-scanning a target accumulates one Evidence per detector per scan pass. The user-facing impact is most visible in the Gap Report's "Unmapped findings" section: the v0.1.2 deep-dive shakedown produced 39 unmapped findings, of which 26 were the LLM honestly labeling rows as "duplicate from another scan pass" / "triplicate from another scan pass." 13 unique findings × 3 scan passes.

**Resolution path:** two reasonable options:

1. **Renderer-only dedupe** — the gap-report writer groups by `(detector_id, source_ref, content)` (excluding `timestamp` from the equality key) and shows only the latest. Cheap; preserves the append-only store. Minor risk: if the user wants drift visibility across scan passes in the *report*, this hides it (they can still walk the store directly).

2. **Canonical-content fix** — exclude `timestamp` from `Evidence`'s canonical hashing. Same content scanned twice → same `evidence_id` → store-level dedup automatic via the content-addressed write path. Bigger semantic change: timestamp becomes metadata rather than content. Tests for `Evidence.evidence_id` stability across timestamps would need to be added; existing tests would need review.

(2) is cleaner long-term. Either way, the agent shouldn't be left to apologize for "duplicate from another scan pass" in user-facing rationales.

**Owner:** Maintainer.

**Target:** v0.2.0. (Not a regression — present since v0.1.0; surfaced as material UX in the v0.1.2 shakedown.)

**Cross-references:** v0.1.2 deep-dive shakedown report; v0.1.3 Bedrock test report.

---

### Prompt-tuning for systematic over-conservatism + cross-thematic citations

**Item:** Two patterns observed across both the v0.1.2 (Anthropic) and v0.1.3 (Bedrock) deep-dive shakedowns against `lhassa8/govnotes-demo`. They're agent-output quality issues, not deterministic bugs:

1. **KSI-RPL-TRC and KSI-SVC-RUD systematically classified `evidence_layer_inapplicable`** despite the codebase having a documented gap that the corresponding detectors *do* surface from IaC (no `aws_backup_restore_testing_plan`, no `aws_s3_bucket_lifecycle_configuration`). The agent treats absence-of-evidence as inapplicability rather than as a `not_implemented` gap. Consistent across both backends, so it's prompt-related, not a Bedrock-vs-Anthropic disposition difference.

2. **Cross-thematic over-attachment.** When a KSI's specific surface is empty, the agent reaches for adjacent evidence: KSI-CNA-MAT and KSI-CNA-RNT both cite the same unparseable-S3-policy evidence (relevant to attack surface and traffic restrictions only loosely); the v0.1.2 shakedown reported KSI-AFR-UCM citing FIPS-TLS evidence (cryptographic-modules vs. transport-confidentiality framing). The Gap Agent's prompt allows liberal evidence citation, which collides with downstream consumers (e.g., remediate's CLI gate strictly filters by `Evidence.ksis_evidenced` — see the existing v0.1.x followup entry).

**Resolution path:** both want a real-customer evidence corpus to tune against — synthetic dogfood produces synthetic priors. Specifically:

- For (1): tighten the Gap Agent's prompt to distinguish "KSI is procedural/unreachable from IaC" from "KSI has an IaC-evidenceable detector, but it produced no Evidence (which is itself a gap)." The current prompt collapses both into `evidence_layer_inapplicable`.
- For (2): tighten the citation discipline — Gap Agent should prefer Evidence whose `ksis_evidenced` includes the KSI being classified, falling back to thematically-adjacent only with explicit "cross-thematic" framing in the rationale.

Empirical validation requires running modified prompts against a real customer's Terraform — not synthetic gaps — so the priors are real.

**Owner:** Maintainer.

**Target:** v0.2.0, blocked on real-customer corpus.

**Cross-references:** v0.1.2 shakedown report; v0.1.3 deep-dive artifact audit; "Gap Agent / Remediate Agent disagree on KSI scope" entry above.

---

### Docker Hub republishing via DSOS

**Item:** `release-container.yml` was configured to publish to both `ghcr.io` and `docker.io` originally. Docker Hub publish was dropped at v0.1.0 because Docker Hub eliminated the free organization tier in 2024 (paid Team is $15/seat/month — overhead a solo-maintainer OSS project doesn't need at launch).

**Resolution path:** apply for the [Docker-Sponsored Open Source](https://www.docker.com/community/open-source/application/) program. Free tier for verified OSS projects, ~2-week application review. Once approved, restore the docker.io publish step in `release-container.yml`, restore the docker-dockerhub cells in `release-smoke.yml`, restore the `docker.io/efterlev/efterlev` reference in `scripts/verify-release.sh` and `docs/RELEASE.md`.

**Owner:** Maintainer.

**Target:** v0.2.0 or earlier.

**Cross-references:** `release-container.yml` leading comment, `LIMITATIONS.md` Docker Hub stanza.

---

### npm namespace utilization

**Item:** the `efterlev` npm namespace was claimed during pre-launch as a placeholder (no published package). Decide whether to publish anything there (e.g., a future JS-side companion library, a JSDOM-based detector, etc.) or release the namespace.

**Owner:** Maintainer judgment call.

**Target:** within first six months — release or use, don't squat indefinitely.

---

### `attestation_format_version` bump policy enforcement

**Item:** `info.attestation_format_version: "1"` was added per SPEC-57.3 with a documented bump policy. No automated check enforces the policy — a maintainer making a breaking change to `AttestationArtifact` might forget to bump.

**Resolution path:** add a `scripts/check-format-version.py` (similar to `scripts/check-docs.py`) that diffs the current schema against the last-tagged-version's schema and fails if the schema changed without a version bump. CI workflow runs it on every PR.

**Owner:** Maintainer.

**Target:** v0.2.0.

---

### SPEC-57.4 — narrative-template consistency

**Item:** Documentation-Agent narratives vary in length and structure across status classes. SPEC-57.4 (deferred from SPEC-57) calls for a consistent template, derived from real-customer artifacts.

**Why deferred:** locking a template before observing real-customer outputs risks over-fitting to dogfood shapes.

**Resolution path:** after first 5–10 real customer scans (or 30 days of public use, whichever comes first), audit narrative outputs and derive a template. Update gap_prompt.md / documentation_prompt.md / remediation_prompt.md per the template.

**Owner:** Maintainer.

**Target:** v0.2.0.

**Cross-references:** `docs/specs/SPEC-57.md` §SPEC-57.4.

---

### Evidence.content typed boundary

**Item:** every detector emits `content: dict[str, Any]` with a per-detector schema documented only in prose under `evidence.yaml`. A detector that adds, removes, or renames a content key silently drifts downstream consumers (Gap Agent, FRMR generator, POA&M generator, ci_pr_summary).

**Resolution path:** each detector module exports a Pydantic content model alongside `detect()`. The `@detector` decorator validates emitted Evidence's content against it. `evidence.yaml` becomes generated documentation, not curated.

**Why deferred:** ~1 day of work spread across 30 detectors.

**Owner:** Maintainer.

**Target:** v0.2.0.

**Cross-references:** Round-2 review finding 3 (DECISIONS 2026-04-25 "Round-2 independent review + 3PAO").

---

### O(1) `evidence_id` → `record_id` index

**Item:** `_validate_claim_derived_from` and the new `resolve_to_record` helper both do an O(N) blob scan when an id doesn't resolve as a `record_id`. At customer scale this could be slow.

**Resolution path:** maintain a SQLite `evidence_id_index(evidence_id, record_id)` table populated alongside writes. Lookup becomes O(1).

**Why deferred:** not measured at scale; current bottleneck is unproven.

**Owner:** Maintainer.

**Target:** v0.2.0 or when real-customer scan times become a concern.

**Cross-references:** Round-2 review finding 4, `src/efterlev/provenance/store.py`.

---

### CR26 baseline_spec_version migration

**Item:** when CR26 lands (mid-2026, est.) FRMR will likely change shape. Efterlev needs to detect, version-gate, and possibly re-attest under the new spec.

**Resolution path:** dedicated SPEC for CR26 migration written when CR26 publishes. The `attestation_format_version` field already exists for downstream consumers to gate by.

**Owner:** Maintainer.

**Target:** within 60 days of CR26 publication.

**Cross-references:** DECISIONS entries for FRMR, SPEC-57.3.

---

### Real PR creation (Drift Agent / `--apply`)

**Item:** Efterlev produces remediation diffs as local output but doesn't apply them or push PRs against remote repos. v0 explicitly out-of-scope (THREAT_MODEL.md).

**Resolution path:** opt-in `--apply` flag on `efterlev agent remediate`; opens a PR against the user's repo with the remediation diff. Threat-model implications need fresh review (writing to remote repos is a new trust boundary).

**Owner:** Maintainer.

**Target:** v0.2.0–v0.3.0, depending on customer pull.

---

### CI regression detection on PRs

**Item:** the existing `pr-compliance-scan.yml` runs Efterlev against the PR's terraform changes. Doesn't yet diff evidence-vs-base-branch — so a PR that introduces a new finding looks the same as a PR that doesn't.

**Resolution path:** scan PR + base, diff the evidence sets, comment only on net-new findings.

**Owner:** Maintainer.

**Target:** v0.2.0.

**Cross-references:** CLAUDE.md "What's next" list.

---

### Context-aware high-entropy redaction patterns

**Item:** `scrubber.py` catches structural secrets (AWS access keys, GitHub tokens, etc. — 7 families). Doesn't catch generic API secrets without known prefixes (`password\s*=\s*"<base64>"` shapes).

**Resolution path:** second-pass detector that flags high-entropy strings adjacent to secret-ish keys. Per LIMITATIONS.md, primary defense remains upstream secret-scanning (trufflehog, gitleaks).

**Owner:** Maintainer.

**Target:** v0.2.0.

---

### POA&M ↔ Remediation Agent integration

**Item:** `efterlev poam` emits POA&M markdown with placeholder `Remediation Plan` fields. `efterlev agent remediate` produces remediation diffs. The two don't talk — POA&M's Remediation Plan field could be auto-populated from prior remediation runs.

**Owner:** Maintainer.

**Target:** v0.2.0.

---

### mkdocs-material blog plugin

**Item:** the launch blog post ("Why we built Efterlev") publishes to dev.to + Medium + a pinned GitHub Discussion at v0.1.0. mkdocs-material's blog plugin is a v0.2.0 follow-up so the docs site itself can carry the blog.

**Why deferred:** locking a blog at v0.1.0 risks over-fitting; dev.to / Medium are the better-trafficked first venues.

**Owner:** Maintainer.

**Target:** v0.2.0 or when the blog has a few posts to seed it with.

---

## Done (resolved)

*Move items here when resolved, with the resolution PR / commit and the date.*

### `efterlev --version` printed stale `0.0.1` from the v0.1.0 wheel — fixed in v0.1.1 (2026-04-29)

Switched `pyproject.toml` to hatch dynamic versioning (`[tool.hatch.version] path = "src/efterlev/__init__.py"`), bumped `__version__` to `"0.1.1"` as the single source of truth, and added `tests/test_smoke.py::test_in_source_version_matches_package_metadata` to lock in the invariant.

### Gap Agent `max_tokens=16384` truncated full-baseline runs — fixed in v0.1.1 (2026-04-29)

Bumped to `32768` (Opus 4.7's output ceiling). Surfaced by a deep-dive shakedown against `terraform-aws-modules/terraform-aws-iam`; the agent's own truncation error message ("increase the max_tokens argument") named the fix.

### Confusing LLM-invocation transcript record polluted the provenance graph — fixed in v0.1.1 (2026-04-29)

`agents.base._invoke_llm` used to write a per-run transcript record with `record_type="claim"` and empty `derived_from` — looked like a malformed Claim and confused provenance walks. Removed; per-claim records (per KSI / per narrative / per remediation) already carry every load-bearing field.
