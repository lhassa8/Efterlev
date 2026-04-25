# SPEC-04: Commit-signing policy

**Status:** docs landed 2026-04-24; branch-protection + DCO-app + key-registration are maintainer actions that complete after the repo transfers to the `efterlev/` org (SPEC-01 remaining sub-task)
**Gate:** A1
**Depends on:** SPEC-02 (maintainer role definition)
**Blocks:** SPEC-05 (release pipeline signs commits it creates), A5 (trust surface — branch protection is part of it)
**Size:** S

## Goal

Every commit on `main` is attributable and tamper-evident, enforced by branch protection, so a downstream auditor or contributor can verify the provenance of any code they're about to run.

## Scope

- SSH commit signing required for maintainers (BDFL-era: the BDFL; post-invitation: all named maintainers per SPEC-02)
- DCO sign-off (`Signed-off-by: ...` line) required for every commit, contributor and maintainer alike, via `git commit -s`
- Branch protection on `main` enforces both: signed commits + DCO sign-off + passing CI + linear history
- DCO sign-off verified by a PR check (GitHub App or equivalent)
- Release tags (`v*.*.*`) are signed
- Maintainer SSH signing keys are registered on the GitHub profile AND recorded in a public `.github/SIGNING_KEYS.md`
- Key-rotation procedure documented

## Non-goals

- GPG signing (SSH signing is simpler, newer, security-equivalent; Git 2.34+ supports it natively)
- Signed commits required for contributor PRs (DCO sign-off is the contributor requirement; signing is encouraged but not enforced, to keep the barrier to first contribution low)
- Custom signing infrastructure (GitHub's built-in SSH-signing support is sufficient)
- CLA (Contributor License Agreement) — we use DCO instead, per `CONTRIBUTING.md`
- In-repo signature verification for historical pre-policy commits (policy applies from the policy-landing commit forward; prior history is unchanged)

## Interface

- Branch protection on `main`, via GitHub settings:
  - Require a pull request before merging (1 approval from a maintainer)
  - Require signed commits
  - Require linear history
  - Require status checks: `tests`, `ruff`, `mypy`, `dco-check`
  - Do not allow bypassing (including administrators)
- `.github/SIGNING_KEYS.md` — public record of maintainer SSH signing keys' public halves (fingerprints + GitHub handle)
- `CONTRIBUTING.md` updated with:
  - DCO paragraph (already present; refined in this spec)
  - SSH-signing setup link for contributors who choose to sign
- Release tags signed via `git tag -s` using the releasing maintainer's SSH key

## Behavior

- **Maintainer commits:** must be both SSH-signed AND DCO-signed-off. Branch protection blocks unsigned commits; the DCO check blocks missing sign-offs.
- **Contributor commits:** must be DCO-signed-off (via `git commit -s`); signing is optional. If a contributor's PR is merged via "squash and merge" (the default merge strategy), the squash commit is created and signed by the merging maintainer, inheriting the contributor's DCO sign-off in the squash-commit body.
- **Default merge strategy:** squash and merge. Rationale: keeps `main` history linear, ensures every `main` commit is signed by a maintainer, preserves contributor authorship and DCO sign-off in the squash-commit message.
- **Release tags:** SSH-signed by the releasing maintainer using `git tag -s`.
- **Unsigned commit pushed to main:** rejected by branch protection; maintainer notified.
- **PR with unsigned-off commits:** DCO check fails; contributor prompted to amend with `git commit -s --amend` or run `git rebase --signoff`.

## Data / schema

N/A (text documents + GitHub settings).

## Test plan

- **Manual, one-time:**
  - Attempt a direct push of an unsigned commit to `main` as a maintainer → rejected.
  - Open a PR with a commit missing `Signed-off-by:` → DCO check fails with a clear error.
  - Open a PR with DCO-signed commits → DCO check passes.
  - Create a release tag via `git tag -s v0.1.0-rc.0` → verify signature with `git verify-tag v0.1.0-rc.0`.
- **Continuous:** branch-protection settings are reviewed quarterly via a maintainer-led check against the spec.

## Exit criterion

### Docs — landed 2026-04-24

- [x] `.github/SIGNING_KEYS.md` exists with structure for the BDFL's SSH signing key's public half and a documented rotation procedure. Public-key text is a `<pending>` placeholder until the maintainer generates the key and commits a signed PR filling it in.
- [x] `.github/BRANCH_PROTECTION.md` exists as the authoritative config record for `main` branch protection — every setting listed with its state (✅ / ⬜) and the rationale deferred to this spec.
- [x] `.github/CODEOWNERS` exists (from SPEC-02) requiring maintainer review on PRs.
- [x] `CONTRIBUTING.md` documents the DCO flow with `git commit -s` invocation and the rationale, plus the SSH-signing config for maintainers. Former DCO blurb in the License section refactored to defer to the new "Signing and DCO sign-off" section.

### Maintainer actions — pending

- [ ] BDFL generates an Ed25519 SSH signing key and registers the public half on their GitHub profile as a Signing Key.
- [ ] BDFL opens a PR (signed with the new key) filling in the `<pending>` section of `.github/SIGNING_KEYS.md`.
- [ ] Repo transfers from `lhassa8/Efterlev` to `efterlev/efterlev` (SPEC-01 remaining sub-task).
- [ ] Branch protection applied to `main` in the `efterlev/efterlev` repo per `.github/BRANCH_PROTECTION.md` checklist.
- [ ] DCO GitHub App installed at `github.com/apps/dco` for the `efterlev/` org.
- [ ] Verification checklist from `.github/BRANCH_PROTECTION.md` "Post-application checklist" run, confirming all four enforcement scenarios are active.

All maintainer actions are ordered: SSH key → key-registration PR → repo transfer → branch-protection config + DCO app install. Each unlocks the next.

## Risks

- **Contributor confusion about DCO.** Mitigation: CONTRIBUTING.md has a one-paragraph explainer + the exact invocation. The DCO-check error message links to it. The first contributor who trips on this gets a maintainer walk-through; subsequent confusion is a docs-clarity bug.
- **Maintainer loses SSH key.** Mitigation: documented key-rotation procedure in `.github/SIGNING_KEYS.md`:
  1. Generate new key pair.
  2. Register public half on GitHub profile.
  3. Open a PR updating `.github/SIGNING_KEYS.md` with the new fingerprint, signed by the BDFL (or a co-maintainer for the BDFL's own rotation).
  4. Revoke old key from GitHub profile.
- **A downstream user needs to verify historical commits.** Accept: pre-policy history is unsigned; we don't retroactively sign. Document this as a known limitation.
- **Branch protection accidentally bypassed by an admin.** Mitigation: "Do not allow bypassing (including administrators)" is set explicitly in the branch-protection config. If a bypass is ever needed, it's documented in `DECISIONS.md` as an exception.

## Open questions

- Do we allow force-push to `main` under any circumstance? Answer: no. Force-push is never allowed on `main`. Rewriting published history is worse than an embarrassing-but-recorded commit.
- Should we require signed commits on release branches? Answer: the project uses tags on `main` rather than release branches, so this is moot. If the policy changes in the future to use release branches, a spec amendment adds the requirement there.
