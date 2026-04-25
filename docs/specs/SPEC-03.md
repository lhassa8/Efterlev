# SPEC-03: CODE_OF_CONDUCT.md

**Status:** implemented 2026-04-24
**Gate:** A1
**Depends on:** SPEC-01 (canonical identity — `conduct@efterlev.com` mailbox), SPEC-02 (GOVERNANCE.md names BDFL role)
**Blocks:** A5 (trust surface)
**Size:** S

## Goal

Adopt a published community Code of Conduct before the repo goes public, with a working enforcement channel and a clear reporting process, so the first visitor who checks for one finds one.

## Scope

- Adopt the Contributor Covenant 2.1 (**by reference to the canonical hosted text**, not reproduced verbatim — see Revision below)
- Project-specific interpretation codifying existing `CONTRIBUTING.md` norms ("no FUD about competitors," "no overclaiming in docs or code," "compliance jargon is okay; gatekeeping is not")
- Enforcement contact: `conduct@efterlev.com` (BDFL inbox during the BDFL era; dedicated maintainer list after the steering-committee trigger in SPEC-02)
- Reporting and resolution process with a response-time commitment
- Cross-references from `CONTRIBUTING.md` and `README.md`

## Revision 2026-04-24: adoption-by-reference instead of verbatim

The original spec said "adopt Contributor Covenant 2.1 verbatim." During implementation, the verbatim text's enumeration of unacceptable behavior tripped a content-filtering output guard on the tool the maintainer was using to author the file. Switched to adoption-by-reference, which is:

- A recognized pattern used by Kubernetes, TensorFlow, and many other major OSS projects.
- Explicitly allowed by the Contributor Covenant maintainers (CC BY 4.0 with attribution).
- Lighter in the repo; auto-tracks upstream errata without a stale local copy.
- Clearer in how the Efterlev-specific interpretation layers on top (it is clearly separate from, not embedded in, the upstream text).

The substantive requirements — clear CoC identification, enforcement contact, response-time commitment, project-specific interpretation — are all met.

## Non-goals

- Writing a custom Code of Conduct (reinventing an existing, battle-tested standard adds no value and costs trust)
- Multiple reporting channels (one is enough; complexity discourages actual use)
- Anonymous-reporting infrastructure beyond email (a privacy-hardened GitHub form is optional post-launch; not blocking)
- Public enforcement log (precedent matters; privacy also matters; no public log at v0.1.0)

## Interface

- `CODE_OF_CONDUCT.md` at repo root
- Structure:
  1. Our Pledge (Contributor Covenant 2.1 verbatim)
  2. Our Standards (Contributor Covenant 2.1 verbatim)
  3. Enforcement Responsibilities (Contributor Covenant 2.1 verbatim)
  4. Scope (Contributor Covenant 2.1 verbatim)
  5. Enforcement (Contributor Covenant 2.1 verbatim; plus `conduct@efterlev.com` as the contact)
  6. Enforcement Guidelines (Contributor Covenant 2.1 verbatim)
  7. **Project-specific interpretation (Efterlev addendum)** — a short section codifying the three norms above, with examples
  8. Attribution (Contributor Covenant 2.1 verbatim)

## Behavior

- Reports sent to `conduct@efterlev.com` are acknowledged within 3 business days.
- Resolution happens privately between the reporter, the subject of the report, and the enforcement body (BDFL alone during the BDFL era; steering committee post-trigger).
- Enforcement actions follow the Contributor Covenant's four-tier ladder (Correction → Warning → Temporary Ban → Permanent Ban).
- Aggregate statistics may be published (e.g., "N reports received, M actions taken during period P") once the project has enough activity to preserve reporter anonymity via aggregation.

## Data / schema

N/A.

## Test plan

- **Rendering:** document renders in the docs site (A6).
- **Link-validation:** `CONTRIBUTING.md` and `README.md` link to `CODE_OF_CONDUCT.md`.
- **Mailbox:** `conduct@efterlev.com` is a live mailbox that the BDFL receives, verified by sending a test email.
- **Review:** document reviewed by at least one non-author reader before merge.

## Exit criterion

- [x] `CODE_OF_CONDUCT.md` exists at repo root, adopting Contributor Covenant 2.1 with the Efterlev project-specific interpretation section. **Done 2026-04-24.**
- [x] `conduct@efterlev.com` is configured and a test email has landed in the BDFL inbox. **Done 2026-04-24** (confirmed by maintainer). `security@efterlev.com` also wired up, satisfying the corresponding sub-task from the still-to-be-written SPEC-30.
- [x] `CONTRIBUTING.md` links to `CODE_OF_CONDUCT.md`. **Done 2026-04-24** — CoC section rewrote to defer to the new file.
- [x] `README.md` links to `CODE_OF_CONDUCT.md`. **Done 2026-04-24** — added to the Contributing section.

## Risks

- **Bad-faith reports weaponizing the CoC.** BDFL judgment is the check during the BDFL era; documented precedent builds over time. The Contributor Covenant's enforcement ladder is proportionate by design.
- **Enforcement decisions are contentious and visible.** Accept: contentious-but-principled enforcement is the correct failure mode for a project that values community over reach.
- **BDFL unavailable when a report arrives.** Mitigation: `conduct@efterlev.com` delivers to multiple addresses once maintainers exist beyond the BDFL. Until then, document the 3-business-day acknowledgment window honestly rather than pretending to 24/7 coverage.

## Open questions

None. Move to `accepted` on review.
