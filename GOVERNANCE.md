# Governance

This document describes how decisions get made in Efterlev, who has authority to make which kind of change, and how that structure evolves as the project grows.

If you are reading this because you want to contribute, see [CONTRIBUTING.md](./CONTRIBUTING.md) for the path from idea to merged PR. This document is about *who decides what*, not about *how to code*.

## Principles

Every governance decision serves these principles. When they conflict, the one listed first wins.

1. **Honest claims over strong claims.** Efterlev is a compliance tool — overclaiming is worse than underclaiming. Governance upholds the product's truth-telling posture: contributions that inflate what the tool proves are reshaped or declined.
2. **Evidence before claims.** Deterministic, scanner-derived output is authoritative; LLM-reasoned output is always a draft requiring human review. Governance upholds this distinction structurally (see `CLAUDE.md` non-negotiable principles and `DECISIONS.md` for the architecture record).
3. **Pure open source, forever.** Apache-2.0 core, no commercial tier, no paid layer, no managed SaaS. Sustained by maintainer time and contributor goodwill. Recorded in `DECISIONS.md` 2026-04-23 "Rescind closed-source lock."
4. **Local-first, no telemetry.** The tool runs where its user tells it to — laptop, CI, GovCloud EC2, air-gap — without phoning home. Governance upholds this at the merge review.
5. **Drafts, not authorizations.** Efterlev never claims to produce FedRAMP authorization. Contributions that blur that line are declined.

## Roles

- **BDFL (Benevolent Dictator For Life)**: `@lhassa8`. Holds final decision authority during the BDFL era. Merges PRs, sets direction, resolves disputes, invites maintainers, and decides when this document's structure changes. "For Life" is a convention — the BDFL can step down at any time; a steering committee forms when the project outgrows single-maintainer governance (see "Steering Committee Trigger").
- **Maintainers**: contributors invited to the merge/review team by the BDFL. Can approve and merge PRs within their area of ownership (defined in `.github/CODEOWNERS`). During the BDFL era, the BDFL is the sole maintainer; the role is defined now so the invitation process is ready when the first external contributor earns it.
- **Contributors**: anyone who opens an issue, submits a PR, writes docs, or participates in discussions. No permissions beyond the GitHub defaults. Contribution is itself participation; becoming a maintainer is not a goal every contributor should pursue.
- **Community**: users of Efterlev who may never open a PR. Their feedback, bug reports, and real-world usage shape the project. Governance accounts for community voice in RFC comment windows and in the issue triage queue.

## Decision-making

Two modes, chosen by the shape of the change.

### Lazy consensus (default)

For routine changes — new detectors, bug fixes, doc improvements, small refactors:

1. A PR is opened.
2. CI runs; checks pass.
3. A maintainer reviews.
4. If there is no objection within a reasonable review window (typically 1–2 weeks for non-trivial changes; same-day for trivial), the PR is approved and merged.

Silence is consent. Active objection — "I don't think this should land" — stops the clock until the objection is resolved.

### RFC (for architectural decisions)

Architectural, cross-cutting, or contract-breaking changes require a written `DECISIONS.md` entry *before or in the same PR as* the implementation. The entry names:

- The decision.
- The rationale.
- Alternatives considered and why they were rejected.
- Tags (`[architecture]`, `[security]`, etc.).

The RFC entry is the review surface. Maintainers and the BDFL review both the entry and the implementation together. Changes that don't warrant a DECISIONS entry are, by definition, not architectural.

Examples of changes that warrant an RFC entry:
- Changes to the detector / primitive / agent contracts.
- New Pydantic model fields on `Evidence`, `Claim`, `ProvenanceRecord`, `AttestationDraft`, `AttestationArtifact`, `EvidenceManifest`, or `PoamClassificationInput`.
- New CLI verb or non-trivial flag.
- New MCP tool or change to an existing MCP tool's JSON schema.
- New LLM backend or change to the backend abstraction.
- On-disk layout changes under `.efterlev/`.
- Changes to the FRMR attestation JSON shape or POA&M markdown shape.

Examples of changes that do not warrant an RFC entry:
- A new detector added inside the existing contract.
- Bug fixes.
- Documentation improvements.
- Test additions or refactors.
- Dependency version bumps.

### Appeals and disagreement

During the BDFL era, the BDFL is the final decision-maker. Appeals to a BDFL decision take the form of a reasoned comment in the relevant issue or PR. The BDFL responds or updates the decision; the record stays public.

After the steering committee forms, appeals follow whatever process the SC adopts.

## Maintainer invitation

There is no application process. Becoming a maintainer is not a rank to pursue; it is a chore assignment for contributors who have earned trust.

**Rough signals that lead to an invitation:**
- Sustained contribution over 3+ months.
- ~10+ merged PRs at the project's quality bar (lint/type/test clean, evidence-vs-claims-discipline upheld, detector READMEs honest about what they don't prove).
- Thoughtful review participation on others' PRs.
- Demonstrated judgment on ambiguous decisions — e.g., knowing when to decline a PR politely rather than patch it through.

Invitation is by the BDFL, via a direct message. The invited contributor can accept or decline. If accepted, the contributor is added to `.github/CODEOWNERS` for their area of ownership (often starting with detectors or docs; widening as trust grows).

**Resignation**: a maintainer can step back by opening a GitHub Discussion stating their intent. No explanation required. The BDFL removes them from `CODEOWNERS` in a subsequent PR.

**Inactive maintainers**: a maintainer with no review or merge activity for 6+ consecutive months may be moved to emeritus status (still listed in `CONTRIBUTORS.md`; removed from `CODEOWNERS`). The move is announced in a GitHub Discussion; the maintainer can object within 30 days.

## Steering Committee Trigger

The BDFL era transitions to a technical steering committee (TSC) when the project has **10 contributors with sustained activity** — defined as at least one merged PR in each of the prior 3 calendar months, sustained for 6 months. When the trigger fires:

1. The BDFL opens a `DECISIONS.md` entry titled "Steering Committee Formation" with a proposed SC structure (membership criteria, election method, term length, BDFL role-transition, meeting cadence).
2. A 30-day public comment window follows, in GitHub Discussions.
3. The entry is finalized and the SC forms per the adopted structure.

The SC-formation specifics are not pre-committed here. They are a decision for the 10+ contributors who have made the project big enough to need them, informed by the BDFL's proposal but not bound by it.

Until the trigger fires, the BDFL makes all decisions the TSC would otherwise make. The trigger is an escape hatch, not a prediction.

## Changes to this document

- **BDFL era**: this document is changed via a normal PR, reviewed and merged by the BDFL. Substantive changes (anything beyond typo fixes) require a `DECISIONS.md` entry explaining the change and its rationale.
- **Post-TSC**: per the process the TSC adopts.

## Foundation home

A future donation to a neutral software foundation (OpenSSF, Linux Foundation, CNCF) remains an option when contributor diversity warrants. The project would retain its Apache-2.0 license; the foundation provides long-term stewardship beyond any single maintainer's time commitment.

This option is explicitly deferred. Revisit when the project has **25+ sustained active contributors** and the TSC has been operational for at least one year.

## Code of Conduct

Governance of interpersonal conduct lives in [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md). Enforcement contact: `conduct@efterlev.com`.

## Where decisions are recorded

- **Routine PRs**: in the PR itself and its merge commit.
- **Architectural decisions**: in `DECISIONS.md`, one entry per decision, chronologically ordered.
- **Non-negotiable principles**: in `CLAUDE.md` and this document.
- **Scope boundaries**: in `docs/icp.md` (who we build for) and `COMPETITIVE_LANDSCAPE.md` (who we don't try to be).
- **Product limitations**: in `LIMITATIONS.md` (updated alongside feature work, not at release).

If a decision isn't in one of those places, it hasn't been made yet.
