# SPEC-07: Composite GitHub Action (efterlev/scan-action)

**Status:** scaffold pushed to `github.com/efterlev/scan-action` (public) 2026-04-24; branch protection applied; self-test green (with skip-gate until Efterlev ships v0.1.0); `v1.0.0` tag + Marketplace listing gated on Efterlev's first real PyPI release
**Gate:** A2
**Depends on:** SPEC-01 (GitHub org owns `efterlev/scan-action`), SPEC-05 (pipx-installable from PyPI), SPEC-06 (container alternative to pipx)
**Blocks:** SPEC-43 (CI integration tutorial references this action)
**Size:** M

## Goal

Consumers wire Efterlev into their PR pipeline with 3 lines of YAML, published at `efterlev/scan-action@v1` on the GitHub Marketplace, so the barrier to "try this in CI" is lower than any competing tool.

## Scope

- Dedicated repo at `github.com/efterlev/scan-action` (top-level repo required for Marketplace listing)
- Composite action at `action.yml` in that repo's root
- Installs Efterlev via pipx (default) or container (opt-in); runs `init` + `scan`; optionally runs `agent gap`; optionally posts a sticky PR comment via `ci_pr_summary.py`
- Versioned releases: `v1`, `v1.0.0`, `v1.1.0`, etc. The moving `v1` tag tracks the latest `v1.x.y`.
- Submitted to the GitHub Marketplace
- Accepts inputs for target directory, baseline, optional agent run, fail-on-finding gating, PR-comment toggle, Efterlev version pin

## Non-goals

- GitLab CI / CircleCI / Jenkins equivalents (separate specs; the underlying `efterlev scan` command works in any CI that can run pipx or Docker, but the sticky-comment UX is GitHub-specific)
- Drift detection in the action (post-launch C1)
- Auto-remediate (post-launch C2)
- Marketplace "verified creator" status (nice to have; not a launch blocker)
- Self-updating — the action pins the Efterlev version; updates are explicit in consumer YAML

## Interface

Consumer YAML:
```yaml
- uses: efterlev/scan-action@v1
  with:
    target-dir: .                          # optional; default cwd
    baseline: fedramp-20x-moderate         # optional; default this
    efterlev-version: '0.1.0'              # optional; default = latest stable
    run-gap-agent: true                    # optional; default false
    fail-on-finding: false                 # optional; default false
    comment-on-pr: true                    # optional; default true (on PR events)
    install-method: pipx                   # optional; 'pipx' | 'container'; default pipx
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}  # required iff run-gap-agent
```

Action outputs:
- `findings-count` — integer total findings across detectors
- `report-path` — path to the HTML report inside the workflow workspace
- `store-dir` — path to `.efterlev/` inside the workflow workspace
- `has-regressions` — boolean (always false at v1.0.0; meaningful once SPEC C1 drift lands)

Files in the scan-action repo:
- `action.yml` — the composite action definition
- `scripts/install.sh` — install logic (pipx branch + container branch)
- `scripts/run-scan.sh` — scan invocation
- `scripts/post-comment.sh` — sticky-comment rendering (shells out to `efterlev`'s in-package `ci_pr_summary` module)
- `README.md` — Marketplace-friendly README with usage examples
- `.github/workflows/test.yml` — tests the action against a known-finding fixture on every PR to the scan-action repo

## Behavior

- Default invocation (no inputs): installs latest stable Efterlev via pipx, runs `efterlev init` (idempotent) + `efterlev scan` against cwd, posts a sticky PR comment summarizing findings, exits 0.
- With `run-gap-agent: true` and `ANTHROPIC_API_KEY` set: also runs `efterlev agent gap` and includes KSI classifications in the sticky comment.
- With `run-gap-agent: true` and `ANTHROPIC_API_KEY` unset: skips the agent step with a clear message in the comment, exits 0.
- With `fail-on-finding: true`: the action exits non-zero if any scan finding appears (regardless of severity). Consumers use this to gate PR merges.
- With `install-method: container`: pulls `ghcr.io/efterlev/efterlev:{efterlev-version}` and runs scan via `docker run`. Useful for air-gap-adjacent CI environments.
- Sticky-comment behavior: same comment updated across reruns on the same PR; not duplicated. Identified by a hidden HTML marker in the comment body.
- Artifacts: `.efterlev/reports/` uploaded as a workflow artifact named `efterlev-report-{run-id}`.
- Non-PR events (push, schedule): scan runs; sticky-comment step is skipped; exit follows `fail-on-finding`.

## Data / schema

- Action inputs/outputs per Interface section.
- Sticky-comment marker format: `<!-- efterlev-scan-action:v1 -->` at the top of the comment body; used to find and update the existing comment.

## Test plan

- **Unit tests in scan-action repo:** shell-script linting (shellcheck) on the install/run/comment scripts.
- **Integration via `.github/workflows/test.yml`:**
  - Matrix of input combinations: default, with run-gap-agent, with fail-on-finding, with container install-method, on non-PR event.
  - Each matrix cell exercises the action against a fixture sub-repo in the scan-action repo (`tests/fixture/` with known-finding Terraform).
  - Assertion: expected findings appear; exit code matches input gating; sticky comment posted exactly once per PR.
- **Version-pin verification:** with `efterlev-version: '0.1.0'`, the action installs exactly that version, not latest.
- **Sticky-comment idempotence:** run the action twice on the same PR; assert the comment was updated, not duplicated.
- **Marketplace listing:** before launch flip, the action's Marketplace page renders cleanly with the expected badges, version selector, and usage snippet.

## Exit criterion

### Scaffold landed 2026-04-24

Scaffold files live at `/tmp/efterlev-scan-action/`, ready to push as the initial commit of the new `efterlev/scan-action` repo. Contents:

- [x] `action.yml` — composite action definition. All 7 inputs + 4 outputs per the Interface section. Branding set (shield icon, blue). Four-step `runs:` (install → scan → post-comment → upload-artifact).
- [x] `scripts/install.sh` — pipx or container install path, version-pinnable via `EFTERLEV_VERSION`.
- [x] `scripts/run-scan.sh` — runs init + scan + optional gap agent; resolves `findings-count`, `report-path`, `store-dir` outputs; honors `fail-on-finding`.
- [x] `scripts/count-findings.py` — standalone sqlite helper that counts finding-shaped evidence records. Replaces an inline Python heredoc for cleaner maintainability (refactored during implementation; see Revision section).
- [x] `scripts/post-comment.sh` — sticky-comment logic via `gh` CLI, find-or-update pattern using an HTML-comment marker.
- [x] `README.md` — Marketplace-ready README with quickstart, full input/output table, `fail-on-finding` warning, air-gap/GovCloud notes, and explicit "what this action does not do" section.
- [x] `LICENSE` — Apache 2.0 (copied from Efterlev main repo).
- [x] `tests/fixture/main.tf` — minimal Terraform with deliberate compliance gaps for self-test.
- [x] `.github/workflows/test.yml` — self-test matrix (pipx x container x fail-on-finding branches) plus a dedicated expected-failure job asserting `fail-on-finding=true` exits non-zero on known findings.
- [x] All shell scripts syntax-checked with `bash -n`; Python helper parses cleanly; both YAML files validated.

### Pushed and protected 2026-04-24

- [x] `efterlev/scan-action` repo created (empty, public).
- [x] Initial scaffold pushed as signed-off commit. Repo description + homepage set.
- [x] Follow-up commit added CODEOWNERS (`* @lhassa8`).
- [x] Follow-up commit added a `check-efterlev-available` skip gate to the self-test workflow, because the pipx and container install paths both require a real Efterlev PyPI release or container image that doesn't exist yet (placeholder `efterlev==0.0.0` is a library, not a CLI — pipx refuses; `ghcr.io/efterlev/efterlev:latest` doesn't exist yet).
- [x] Self-test workflow green (matrix cells gracefully skip when Efterlev version is 0.0.0).
- [x] Branch protection applied: PR required (0 approvals during BDFL era — solo maintainer can't self-approve), linear history, no force-push, no deletion, `enforce_admins: true`, required status check = `Check if Efterlev has a real PyPI release`, conversation resolution required. Signed-commit requirement parked until BDFL SSH key lands per SPEC-04.

### Gated on Efterlev v0.1.0 shipping first

- [ ] Remove the `check-efterlev-available` skip gate (or leave it; it harmlessly returns `skip=false` once Efterlev is past 0.0.0).
- [ ] Self-test matrix runs end-to-end (both pipx and container install paths) against a real Efterlev release.
- [ ] Tag `v1.0.0` and cut a GitHub Release.
- [ ] Submit to GitHub Marketplace (Settings → Marketplace → Publish Marketplace draft).
- [ ] Sample integration verification: create a test consumer repo, add the 3-line YAML, open a PR, confirm sticky comment lands.
- [ ] Bump required status checks to include the full matrix cell names once they run.
- [ ] Flip `required_signatures` to `true` on branch protection once the BDFL's SSH signing key is registered per SPEC-04.
- [ ] Bump `required_approving_review_count` to 1 and enable `require_code_owner_reviews` once the first co-maintainer is invited per GOVERNANCE.md.

## Revision 2026-04-24: Python extracted to a helper file

The draft had the sqlite-querying Python inlined as a bash heredoc inside `$(...)` command substitution in `run-scan.sh`. That pattern is valid in bash 5.x (what GitHub runners use) but trips bash 3.2 (what ships on macOS). Extracting the Python to a standalone `scripts/count-findings.py` avoids the ambiguity, passes syntax-check on both bash generations, and is cleaner code — the Python gets its own file with proper docstring and imports rather than being wedged into a shell script via heredoc.

No functional change; purely a packaging refactor. Documented here because the refactor is visible in the file tree.

## Risks

- **Marketplace review delay.** Mitigation: submit early in A2 work; Marketplace review is typically 1–3 days.
- **Action + efterlev version drift.** Consumers use `@v1` moving tag which tracks `v1.x.y`; the action pins Efterlev to a known-compatible version. When Efterlev ships a breaking change, `v2.x.y` of scan-action tracks it; `v1` is frozen.
- **Sticky-comment GitHub API changes.** Accept: low-frequency risk; mitigate with integration tests that catch breakage before users do.
- **ci_pr_summary.py lives in the main repo but the action lives in scan-action.** Mitigation: the action shells out to `efterlev ci-summary` (CLI subcommand to be added in a small follow-up spec) or runs `python -m efterlev.scripts.ci_pr_summary` directly from the installed package. One source of truth.
- **Maintainer time split between two repos.** Accept: scan-action is thin enough that issues will be infrequent. If traffic picks up, add a maintainer per SPEC-02.

## Open questions

- Do we ship a GitLab CI equivalent at launch? Answer: no. GitLab-CI recipe lives in docs (SPEC-43) but isn't a Marketplace-style action. Separate spec post-launch if demand surfaces.
- Should scan-action's test fixture live inline in the scan-action repo, or pull from the govnotes demo repo? Answer: inline in scan-action — keeps scan-action independently testable without cross-repo dependency.
- What version of Efterlev does `@v1` default to when `efterlev-version` is unspecified? Answer: the latest stable (non-rc) Efterlev version available on PyPI at the time the scan-action release was cut. The action's README documents which Efterlev version each `v1.x.y` release tracks.
