# SPEC-30: A5 trust surface — omnibus

**Status:** mostly implemented 2026-04-25 — 7 of 8 sub-deliverables landed (30.1, 30.2, 30.3, 30.4, 30.6, 30.7 complete; 30.8 template landed awaiting reviewer sign-off; 30.5 maintainer-action-pending post-repo-transfer)
**Gate:** A5
**Depends on:** SPEC-01 (security@efterlev.com mailbox), SPEC-02 (governance), SPEC-04 (signing policy already documented)
**Blocks:** Launch (gate A5 exit criterion is "a hostile security reviewer with two hours can't find a trust gap that isn't already named here")
**Size:** L when measured by deliverable count; each individual deliverable is S to M.

## Why one omnibus spec

The A5 sketches are 8 small deliverables that share a coherent goal but ship as different artifact types: two Markdown policy docs, two repo-config artifacts (templates, branch protection), two CI workflows (Dependabot/Renovate, security scanning), and two procedural items (PR template, pre-launch review). Each is small enough that an individual SPEC file would be ceremony; collectively they need shared context (what we're trying to convince a reviewer of) plus per-deliverable exit criteria. Same pattern as SPEC-14.

## Goal

A hypothetical hostile security reviewer arriving at the public Efterlev repo for the first time, with two hours to spend, finds every trust signal they expect: clear disclosure path, current threat model, structured contribution surface, enforced branch protection, supply-chain hygiene tooling, security-relevant CI, and an attestation that the maintainer ran a structured pre-launch review.

The reviewer's questions we answer:

1. Where do I report a vulnerability? → SPEC-30.1 SECURITY.md
2. What threats does the maintainer think apply? → SPEC-30.2 THREAT_MODEL.md
3. How do I file a useful issue? → SPEC-30.3 issue templates
4. What's expected of a PR? → SPEC-30.4 PR template
5. Can someone quietly push to main? → SPEC-30.5 branch protection (cross-references SPEC-04)
6. Who watches the dependencies? → SPEC-30.6 Dependabot
7. What scans run on every PR? → SPEC-30.7 CI security scanning
8. Did the maintainer actually look? → SPEC-30.8 pre-launch review record

## Shared exit criteria

A5 closes when:

- Every deliverable below is checked-off `[x]`.
- A non-author reader (or the maintainer themselves with fresh eyes) walks the public-facing trust surface and reports zero gaps.
- All deliverables are present at the moment the repo flips public per the A8 launch rehearsal — not a deliverable lands "soon after launch."

## Sub-specs

### SPEC-30.1 — `SECURITY.md` + coordinated-disclosure process ⬜

**Goal:** A SECURITY.md at repo root that names the disclosure channel, response-time commitment, scope, and supported versions.

**Content (in order):**
1. Reporting a vulnerability — `security@efterlev.com` mailbox + GitHub Security Advisories private-vulnerability-reporting feature; explicit "do not file as public issues."
2. Response-time commitment — acknowledge within 3 business days; status updates every 7 days.
3. Coordinated disclosure window — 90 days default; longer if the issue is a third-party dependency we can't fix unilaterally; shorter if the issue is being actively exploited.
4. Scope — what's in scope (the published Efterlev codebase, the GitHub Action, the container image, the PyPI release artifacts) and what's not (third-party dependencies — those go to their respective projects; LLM provider issues — those go to Anthropic / AWS).
5. Supported versions — at v0.1.0, only the latest minor line. Promote to a "current and previous" model later.
6. Hall of fame — explicitly NOT a paid bug bounty (pure-OSS posture); recognition for reporters who follow the process.

**Exit criterion:**
- [x] `SECURITY.md` exists at repo root.
- [x] Linked from `README.md` and `CONTRIBUTING.md`.
- [x] `security@efterlev.com` is a working mailbox (confirmed during SPEC-03).
- [ ] GitHub Security Advisories is enabled on the public repo at flip time. _(Maintainer action; happens at A8 launch rehearsal.)_

### SPEC-30.2 — `THREAT_MODEL.md` public-repo refresh ⬜

**Goal:** The existing THREAT_MODEL.md is reviewed top-to-bottom against the post-launch posture: code is public, attacker can read internals, attacker can open PRs, attacker can target the supply chain.

**Refreshes needed (specific changes):**
- Threat T-N (TBD-numbered): "Attacker reads source to find prompt-injection paths." Mitigation: per-run-nonced fences (already exists), secret redaction (already exists), public threat-model + invitation to file SAS reports.
- Threat T-N+1: "Attacker submits a malicious PR (e.g., backdoor in a detector or an agent prompt)." Mitigation: branch protection + signed-commit policy (SPEC-04 + SPEC-30.5); maintainer review on every PR; CODEOWNERS gating.
- Threat T-N+2: "Attacker poisons a dependency we trust." Mitigation: pinned dep versions in pyproject.toml, Dependabot (SPEC-30.6), pip-audit in CI (SPEC-30.7).
- Threat T-N+3: "Attacker tampers with a release artifact." Mitigation: Sigstore signing + SLSA provenance (SPEC-08), `verify-release.sh` script.
- Section: "What changes when the repo goes public" — name the deltas explicitly so a future reader can audit the post-launch threat-model evolution.

**Exit criterion:**
- [x] Existing THREAT_MODEL.md threats reviewed; gaps for the public-repo posture filled.
- [x] Four new public-posture-specific threats named with mitigations: T7 (source-review prompt-injection), T8 (malicious PR), T9 (dependency poisoning), T10 (release-artifact tampering).
- [x] Cross-links updated to SECURITY.md, with new "What changes when the repo goes public" section.

### SPEC-30.3 — Issue templates ⬜

**Goal:** Four GitHub issue templates at `.github/ISSUE_TEMPLATE/` so a contributor or reporter has a clear shape for each kind of issue.

**Templates to ship:**
- `bug_report.md` — bug-report shape: env (OS, Python, install method), reproduction steps, expected vs actual, scan-store snippet (sanitized).
- `detector_proposal.md` — new-detector proposal: capability, AWS resource type, KSI/control mapping, fixture sketch, what-it-does-not-prove draft.
- `documentation.md` — docs improvement: page, line, what's wrong, suggested wording.
- `config.yml` — disables blank issues, points security reports at SECURITY.md (NOT to issues).

**Exit criterion:**
- [x] Three templates plus a config.yml exist in `.github/ISSUE_TEMPLATE/` (bug_report.md, detector_proposal.md, documentation.md, config.yml).
- [x] `config.yml` disables blank issues and contact-links to SECURITY.md for vuln reports + GitHub Discussions for open questions.
- [ ] Smoke-tested by clicking "New Issue" — maintainer verifies UI at A8 launch rehearsal.

### SPEC-30.4 — PR template ⬜

**Goal:** A `.github/pull_request_template.md` that reminds contributors of every standard the repo enforces, so a half-finished PR doesn't burn maintainer review time.

**Checklist content:**
- [ ] Description of change + rationale.
- [ ] Tests added or updated (unit / integration / e2e as applicable).
- [ ] `ruff check` + `ruff format --check` clean.
- [ ] `mypy --strict` clean.
- [ ] DCO sign-off on every commit (`git commit -s`); commit signing if you have it set up (optional for contributors).
- [ ] CHANGELOG entry added under the appropriate version section.
- [ ] DECISIONS.md entry added if the change is architectural.
- [ ] For new detectors: all 5 contract files present; "does NOT prove" section in the docstring.
- [ ] For docs changes: links validated; quickstart still passes if touched.
- [ ] Linked issue (if one exists).

**Exit criterion:**
- [x] `.github/pull_request_template.md` exists.
- [x] Checklist covers every gate in `CONTRIBUTING.md`'s "Contribution standards" section, plus type-of-change selector, new-detector contract checklist, and docs-changes checklist.

### SPEC-30.5 — Branch protection + signed-commit enforcement ⬜

**Goal:** Re-confirm that the branch-protection config from SPEC-04 (`.github/BRANCH_PROTECTION.md`) is applied to the `main` branch of `efterlev/efterlev` once the repo transfers, with no drift.

This is mostly a maintainer action, not a doc-write. SPEC-04 already wrote the policy and the audit checklist; SPEC-30.5 is the closure step that confirms the config is live.

**Exit criterion:**
- [ ] Repo transferred to `efterlev/efterlev` per SPEC-01.
- [ ] Branch protection applied per `.github/BRANCH_PROTECTION.md` checklist.
- [ ] DCO GitHub App installed for the org.
- [ ] Verification checklist (4 tests in `BRANCH_PROTECTION.md` "Post-application checklist") run and passed.
- [ ] Required-signed-commits flipped on once the BDFL SSH signing key is registered (separately tracked in SPEC-04 maintainer-action queue).

### SPEC-30.6 — Dependabot config ⬜

**Goal:** Dependabot watches Python deps, GitHub Actions versions, and Docker base-image versions. Updates flow as PRs the maintainer reviews like any other contribution.

**Files:**
- `.github/dependabot.yml` with three update ecosystems: `pip` (weekly, on `main`), `github-actions` (weekly), `docker` (weekly, scoped to the Dockerfile).
- Group config: minor + patch updates grouped into one PR per ecosystem; major updates as individual PRs.
- Auto-rebase enabled.
- Label `dependencies` on every PR.

**Exit criterion:**
- [x] `.github/dependabot.yml` merged with three ecosystems (pip, github-actions, docker), weekly cadence, grouped minor/patch updates, open-PR limits set.
- [ ] Once the repo is public, Dependabot's first scan completes and at least one informational PR opens. _(Maintainer verifies at A8 launch rehearsal.)_

### SPEC-30.7 — CI security scanning ⬜

**Goal:** A `.github/workflows/ci-security.yml` runs on every PR with three industry-standard checks:

1. **`pip-audit`** — Python supply-chain vulnerability scan against the project's resolved dependency set.
2. **`bandit`** — Python static analysis for security issues. Configured to skip false-positive-prone checks (`B101 assert-used` in tests, `B404 import-subprocess` in our scripts).
3. **`semgrep`** — security-focused rule set. Use `r/python.lang.security` plus a small project-specific rule set (e.g., enforce that secret-redaction calls run before LLM dispatch — SPEC-30.7 is the place to encode that as a semgrep rule).

All three required for merge once the workflow is added to branch protection (SPEC-30.5 update once a bug is found).

**Exit criterion:**
- [x] `.github/workflows/ci-security.yml` exists with four jobs: `pip-audit`, `bandit`, `semgrep`, `codeql`.
- [ ] All four scans run cleanly on the public-flip commit. _(Maintainer verifies once the repo goes public — workflows can't run on a private repo without burning Actions minutes.)_
- [ ] Required status check entries added to branch protection at the next audit cadence per `.github/BRANCH_PROTECTION.md`.

### SPEC-30.8 — Pre-launch security review ⬜

**Goal:** A structured walkthrough document attesting that the maintainer (and ideally a second reviewer) reviewed the security-relevant surface before flipping public.

**Content (Markdown, lives at `docs/security-review-2026-XX.md`):**
- Date + reviewer + commit SHA.
- Threat-model coverage walk: each named threat in THREAT_MODEL.md → status (mitigated / accepted-residual-risk / open-with-tracker).
- Dependency review: snapshot of `pip-audit` output at review time, any waived findings explained.
- Secret-handling review: confirm `scrub_llm_prompt` runs unconditionally on all egress paths; spot-check at least 3 detector / agent code paths.
- Provenance review: confirm `validate_claim_provenance` is wired at `ProvenanceStore.write_record` for `record_type="claim"`.
- Build review: confirm release pipelines (release-pypi.yml, release-container.yml, release-smoke.yml) all use OIDC + Sigstore; no long-lived credentials anywhere.
- Open issues: anything found during review that didn't make the launch cut, with a tracked GitHub issue.

**Exit criterion:**
- [x] `docs/security-review-2026-04.md` template exists at repo root with all 7 sections populated (threat coverage, dep review, secrets, provenance, build/release, public-repo posture, open items).
- [ ] Reviewer signs off (commit SHA + handle filled in the doc). _(Maintainer action at A8 launch rehearsal.)_
- [ ] Any open items have GitHub issues filed and labels applied. _(Filled in during the actual review.)_

## Roll-up exit criterion (gate A5)

- [ ] Every sub-spec checked-off above.
- [ ] A non-author reader walks the public-facing trust surface and reports zero gaps in 2 hours.
- [ ] Cross-links between SECURITY.md, THREAT_MODEL.md, CONTRIBUTING.md, GOVERNANCE.md, BRANCH_PROTECTION.md all resolve.
- [ ] LIMITATIONS.md updated to reflect the post-A5 trust posture (no deferred trust items remaining beyond what's documented as v1.5+ scope).

## Risks

- **Scope creep on the threat model.** The THREAT_MODEL.md refresh can spiral into a "let me reanalyze everything" exercise. Mitigation: SPEC-30.2 names exactly four new public-posture threats; expanding beyond requires a follow-up entry, not a SPEC-30 amendment.
- **Pre-launch review treated as a checkbox.** Mitigation: the review document records concrete spot-check evidence per area, not just "I looked at it." A reviewer rubber-stamping the doc is filable as a CoC issue.
- **CI security scans flag false positives that block PRs forever.** Mitigation: bandit and semgrep configs explicitly waive known-false-positive rules with comments naming why; new false positives become PR-level allowlist additions documented in the same file.
- **Dependabot fatigue.** Weekly cadence × three ecosystems × grouped-updates is the calibration that reduces noise. If still noisy, drop to monthly for non-security updates; security updates always at weekly minimum.

## Open questions

- Should SPEC-30.8 (pre-launch review) be repeated post-launch on a recurring cadence (quarterly?), or is it a one-time pre-launch artifact? Answer: one-time pre-launch + opportunistic re-runs when major surface changes ship. Recurring quarterly cadence is overkill for a project our size; revisit if external review demand surfaces.
- Should we add CodeQL (GitHub's free security analysis) alongside bandit + semgrep? Answer: yes, low-cost addition. Add as SPEC-30.7's fourth scan in the implementation.
