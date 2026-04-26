# Branch protection on `main`

**Status (2026-04-26):** applied. The active rule on `efterlev/efterlev` is GitHub **Ruleset** id `15566618` (the newer Rulesets UI, not the older "Branch protection rules"). API verification:

```
gh api /repos/efterlev/efterlev/rulesets/15566618 --jq '{name, enforcement, target, bypass_actors, rules: [.rules[].type]}'
```

returns name=`main`, enforcement=`active`, target=`branch`, bypass_actors=`[]`, rules=`["deletion","non_fast_forward","required_linear_history","required_signatures","pull_request","required_status_checks"]`.

This document is the **authoritative record of the intended config** — if the live ruleset drifts from what's described below, the change is out-of-band and caught at the next audit. Rationale for each setting lives in [SPEC-04](../docs/specs/SPEC-04.md).

## Where to manage

Settings → Rules → Rulesets → "main" → Edit. (NOT Settings → Branches → Branch protection rules — that's the older UI; we used the newer Rulesets system because it's GitHub's recommended path for new repos and has more capabilities like deployment-tag patterns and per-actor bypass lists.)

## Configuration applied

### Require a pull request before merging

- ✅ Require a pull request before merging
  - **Require approvals: 0 during the BDFL era** (a sole maintainer cannot approve their own PRs on GitHub; 0 still requires a PR but waives the count). Bump to 1 when the first co-maintainer is invited per `GOVERNANCE.md`.
  - ✅ Dismiss stale pull request approvals when new commits are pushed
  - ⬜ Require review from Code Owners — **off during BDFL era** (same reason as above — a sole code owner cannot approve their own PR). Flip on at the same time as bumping the approval count.
  - ⬜ Require approval of the most recent reviewable push — **off during BDFL era**; flip on with co-maintainers.

### Require status checks

- ✅ Require status checks to pass before merging
  - ✅ Require branches to be up to date before merging
  - Required checks (names must match the **job display names** exactly as
    they appear in the Checks tab of any PR):
    - `lint, type-check, test` — the single combined job in `.github/workflows/ci.yml`
      that runs `ruff check`, `ruff format --check`, `mypy src/efterlev`, and
      `pytest`. One job rather than four because the venv setup amortizes
      cleanly and CI feedback is faster.
    - `check-docs` — the doc-vs-code drift checker in
      `.github/workflows/check-docs.yml` (numeric claims, CLI references).
    - `DCO` — emitted by the DCO GitHub App on every PR commit; confirms the
      `Signed-off-by:` trailer matches the commit author.
    - Optional / consider adding once they have a track record on PRs:
      `pip-audit`, `bandit`, `semgrep`, `analyze (python)` from
      `.github/workflows/ci-security.yml`. Held off for now because the
      security scanners can have intermittent infrastructure issues; making
      them PR-blocking before observing a few weeks of runs risks false-fail
      friction.

  **Note on autocomplete:** GitHub's branch-protection UI auto-suggests
  status check names from checks that have run on the repo recently. If
  `lint, type-check, test` isn't in the dropdown yet, push any branch + open
  a draft PR to trigger CI once, then return to branch protection — the
  name will appear. Or type the exact name; GitHub accepts unsuggested
  names and binds when CI starts emitting them.

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

## DCO app installation

**Status (2026-04-26):** installed. App slug `dco`, scoped to `efterlev/efterlev` only. Verify:

```
gh api /orgs/efterlev/installations --jq '.installations[] | select(.app_slug=="dco") | {repository_selection, suspended_at}'
```

Should return `repository_selection: "selected"`, `suspended_at: null`.

The DCO app provides the `DCO` required status check by reading each PR commit's `Signed-off-by:` trailer against the commit author. Install URL: https://github.com/apps/dco. Fallback if the app is ever unavailable: `christophebedard/dco-check` or equivalent in a `.github/workflows/dco.yml`.

## Post-application checklist (validated)

Each row was validated end-to-end during the post-Phase-2 setup:

1. **Signed-commit enforcement** — verified by PR #12 (the first signed commit pushed via the new SSH-key-based signing flow). Unsigned commits would fail the `Require signed commits` rule; the PR shows the signature as Verified in GitHub's UI.
2. **DCO enforcement** — every signed commit landing in this repo carries `Signed-off-by: ` from the `git commit -s` flag. The DCO app reports green on every PR.
3. **CODEOWNERS enforcement** — N/A during BDFL era (the rule's `require_code_owner_review` is off). Re-validate when a co-maintainer joins.
4. **Required CI** — verified by the `ci/seed-branch-protection-checks` PR (later closed) firing `lint, type-check, test`. PR #15 exercised the full required-check set on a real change.

## Audit cadence

Review this file against the actual ruleset configuration quarterly (every 3 months). The authoritative API call is `gh api /repos/efterlev/efterlev/rulesets/15566618`. If anything drifts, open a PR either updating the file or reverting the UI change, depending on which represents the actual intended state.

The audit is a chore assignment for a maintainer; during the BDFL era, it falls to the BDFL.
