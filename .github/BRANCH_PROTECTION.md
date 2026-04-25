# Branch protection on `main`

This document records the branch-protection configuration that must be applied to `main` once the repo is transferred to the `efterlev/` GitHub org (per SPEC-01's remaining sub-task). It is the **authoritative record of the config** — if someone changes a setting in the GitHub UI without updating this file, the change is out-of-band and caught at the next audit.

Rationale for each setting lives in [SPEC-04](../docs/specs/SPEC-04.md).

## Settings to apply

Apply all of these on the `main` branch via GitHub UI → Settings → Branches → Branch protection rules → Add rule.

### Require a pull request before merging

- ✅ Require a pull request before merging
  - **Require approvals: 0 during the BDFL era** (a sole maintainer cannot approve their own PRs on GitHub; 0 still requires a PR but waives the count). Bump to 1 when the first co-maintainer is invited per `GOVERNANCE.md`.
  - ✅ Dismiss stale pull request approvals when new commits are pushed
  - ⬜ Require review from Code Owners — **off during BDFL era** (same reason as above — a sole code owner cannot approve their own PR). Flip on at the same time as bumping the approval count.
  - ⬜ Require approval of the most recent reviewable push — **off during BDFL era**; flip on with co-maintainers.

### Require status checks

- ✅ Require status checks to pass before merging
  - ✅ Require branches to be up to date before merging
  - Required checks (names must match CI job names exactly):
    - `tests` (pytest)
    - `ruff` (lint + format)
    - `mypy` (type check)
    - `dco-check` (DCO sign-off verification — the DCO GitHub App's check)
    - additional checks added as they land (bandit/semgrep per SPEC-36, etc.)

### Require signed commits

- ✅ Require signed commits

### Require linear history

- ✅ Require linear history

### Require deployments — not used

- ⬜ Require deployments to succeed before merging — off

### Lock branch — not used

- ⬜ Lock branch — off (read-only isn't our model)

### Restrictions

- ⬜ Restrict who can push to matching branches — off (branch protection + required PR review is sufficient)
- ✅ **Do not allow bypassing the above settings** — on (includes administrators). No exceptions without a `DECISIONS.md` entry recording the exception and why.

### Rules applied to everyone

- ✅ Restrict pushes that create matching branches — off (doesn't apply to main, only to pattern-matching)
- ⬜ Allow force pushes — **off** (force push to main is not allowed under any circumstance per SPEC-04)
- ⬜ Allow deletions — **off**

## DCO check installation

The `dco-check` status check requires installing a DCO verifier on the repo. Two options:

1. **DCO GitHub App** (recommended): Install from https://github.com/apps/dco and enable for the `efterlev` org. App checks each PR commit for a `Signed-off-by:` trailer matching the commit author.
2. **Custom GitHub Action** (fallback): use `christophebedard/dco-check` or equivalent in `.github/workflows/dco.yml` if the app isn't preferred.

Install the DCO app during the same session as applying branch protection; otherwise the `dco-check` required status check will block merges before the app exists to satisfy it.

## Post-application checklist

Run these after applying the settings to verify they're active:

1. **Signed-commit enforcement:** push an unsigned commit directly to `main` (via a bypass test on a scratch branch, then attempt to merge via PR with force-unsigned commit) — GitHub rejects.
2. **DCO enforcement:** open a test PR with a commit missing `Signed-off-by:` — `dco-check` fails; merge is blocked.
3. **CODEOWNERS enforcement:** open a test PR touching a file `.github/CODEOWNERS` marks as BDFL-owned without a BDFL review — merge is blocked.
4. **Required CI:** open a test PR that deliberately fails ruff — merge is blocked.

## Audit cadence

Review this file against the actual GitHub Branch protection rule settings quarterly (every 3 months). If anything drifts, open a PR either updating the file or reverting the UI change, depending on which represents the actual intended state.

The audit is a chore assignment for a maintainer; during the BDFL era, it falls to the BDFL.
