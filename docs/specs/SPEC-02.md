# SPEC-02: GOVERNANCE.md

**Status:** implemented 2026-04-23
**Gate:** A1
**Depends on:** SPEC-01 (canonical identity)
**Blocks:** SPEC-03 (CoC enforcement contact references governance), SPEC-04 (maintainer-signing policy references maintainer role definition), A5 (trust surface builds on governance)
**Size:** S

## Goal

Document how decisions get made, who has commit rights, and what triggers governance evolution, so the open-source project has a published answer to "who's in charge and how does that change" before a public contributor ever asks.

## Scope

- `GOVERNANCE.md` at repo root
- Roles: BDFL, maintainers, committers, contributors, community
- Decision process: lazy consensus for routine changes; RFC-style process for architectural changes (existing `DECISIONS.md` serves as the ADR log)
- Maintainer invitation criteria and process
- Steering-committee formation trigger
- Change process for `GOVERNANCE.md` itself (meta-governance)
- Code-of-conduct enforcement pointer (to `CODE_OF_CONDUCT.md`)

## Non-goals

- Foundation donation process (referenced only; the pure-OSS posture and eventual-foundation-home option are named but not operationalized here)
- Formal voting infrastructure (lazy consensus is the mechanism through the BDFL era)
- Financial/sponsorship governance (pure OSS — no money changes hands, nothing to govern)
- Compensation structure for maintainers (none; this is volunteer-time-funded)
- Sub-project governance (the repo is one project; no sub-project concept yet)

## Interface

- `GOVERNANCE.md` at repo root
- Sections:
  1. Principles (pure-OSS posture, honesty over marketing, evidence-vs-claims discipline)
  2. Roles (BDFL, maintainer, committer, contributor, community)
  3. Decision-making (lazy consensus, RFC process via `DECISIONS.md`, appeals)
  4. Maintainer invitation (criteria, nomination, confirmation, resignation)
  5. Steering-committee trigger (10 sustained active contributors for 90 days)
  6. Changes to this document (BDFL-era: BDFL decides; post-SC: SC vote)
  7. Foundation-home option (explicitly deferred, revisit at 25+ contributors)
- `CODEOWNERS` at `.github/CODEOWNERS` listing the BDFL and current maintainers for the whole repo

## Behavior

- Routine PRs: merged when a maintainer approves and CI passes (lazy consensus).
- Architectural changes: require a `DECISIONS.md` entry before or in the same PR as the implementation. Entry names alternatives considered and rejected.
- Maintainer disagreement: BDFL is the tiebreaker during the BDFL era.
- Maintainer invitation: after sustained high-quality contribution (roughly 10+ merged PRs over 3+ months, consistent review-quality bar, demonstrated judgment), the BDFL invites the contributor. No application process; no self-nomination.
- Steering-committee trigger: when the project has 10+ contributors with sustained activity (at least one merged PR in each of the prior 3 calendar months), the BDFL schedules a steering-committee formation discussion via a `DECISIONS.md` entry. SC membership criteria, election process, and BDFL role-transition are defined in that discussion, not pre-committed here.

## Data / schema

N/A (text document).

## Test plan

- **Rendering:** the document renders correctly via the docs-site build (A6).
- **Link-validation:** every internal link resolves; every external link resolves at render time (broken-link checker in CI).
- **Review:** at least one non-author reader reviews the document before merge. Not automated; recorded in PR comments.

## Exit criterion

- [x] `GOVERNANCE.md` exists at repo root. **Done 2026-04-23.**
- [x] It names the BDFL by handle (`@lhassa8`).
- [x] It states the steering-committee trigger — refined during drafting to "10 contributors with at least one merged PR in each of the prior 3 calendar months, sustained for 6 months," stricter than the original 90-day draft because sustained contribution matters more than brief activity.
- [x] It states the criteria for maintainer invitation (sustained 3+ months, ~10+ merged PRs at quality bar, thoughtful review participation, demonstrated judgment).
- [x] It links to `CODE_OF_CONDUCT.md` (SPEC-03, landing next) and `DECISIONS.md`.
- [x] `.github/CODEOWNERS` exists with the BDFL as owner of the full repo (`* @lhassa8`).
- [x] `CONTRIBUTING.md` "How maintainer status works" section refactored to defer to `GOVERNANCE.md`.
- [x] `README.md` "Governance" section refactored to link to `GOVERNANCE.md`.

## Risks

- **Vague decision process invites bikeshedding.** Mitigation: "BDFL has final say during the BDFL era" is stated explicitly. No false democracy.
- **Maintainer criteria perceived as gatekeeping.** Mitigation: criteria are written as positive signals ("sustained PRs, consistent quality, demonstrated judgment"), not thresholds. Invitation is by the BDFL, with transparent reasoning documented in the nomination (even if not the invitation conversation itself).
- **Steering-committee trigger never fires because contribution stays thin.** Accept: if the project doesn't grow that far, BDFL governance is sufficient indefinitely. The trigger is an escape hatch, not a prediction.

## Open questions

None.
