# SPEC-53: A7 deployment-mode verification matrix — omnibus

**Status:** implemented 2026-04-25 — matrix doc + runbook template landed; ⚪→🟡 graduations happen continuously post-launch as maintainers and customers walk modes
**Gate:** A7
**Depends on:** SPEC-09 (release-smoke.yml — covers most CI-able modes), SPEC-12 (GovCloud deploy tutorial), SPEC-13 (Bedrock smoke test)
**Blocks:** A8 launch rehearsal
**Size:** M — mostly documentation; the CI matrix is already shipped via SPEC-09.

## Why one omnibus spec

A7 is largely confirmation work — making explicit which deployment modes CI covers, which modes need manual verification, and the runbook to walk a manual mode. SPEC-09 already implements the CI matrix; A7 records its scope and adds the manual-verification ritual for modes CI can't cover. Heavy on documentation, light on new code.

## Goal

Every deployment mode the project claims to support has either:

- An automated CI smoke that runs on every release-candidate tag (verified continuously), or
- A written, reproducible manual-verification runbook with a dated "last verified" stamp.

A reader checking "does Efterlev work on Linux ARM containers in GovCloud EC2?" finds a definitive answer in `docs/deployment-modes.md`, not "we'll get back to you."

## Sub-specs

### SPEC-53.1 — Deployment-mode matrix doc ✅ (landed 2026-04-25)

`docs/deployment-modes.md` — the canonical matrix. Lists every supported mode with one of three statuses:

- **CI-verified.** Covered by `release-smoke.yml` (SPEC-09) on every tag; records the matrix cell name.
- **Manually verified.** Walked through by a human; records date, version, and any caveats found.
- **Documented but unverified.** Pattern is described but never end-to-end-confirmed by anyone yet — honest state for v0.1.0 launch.

**Table columns:**
- Mode (host OS/arch + install method)
- Verification type (CI / manual / documented-only)
- Latest verification (commit SHA + date OR "release-smoke matrix")
- Notes (gotchas, OS-specific quirks)

### SPEC-53.2 — Manual verification runbook template ✅ (landed 2026-04-25)

`docs/manual-verification-runbook.md` — a generic template for any new deployment mode. Sections:

1. Pre-flight: what's required (OS, hardware, AWS account, etc.)
2. Setup: install commands, config commands.
3. Smoke test: minimal command that exercises scan → agent gap.
4. Pass criteria: explicit checks (exit codes, files produced).
5. Cleanup: leave-no-trace teardown.
6. Record: where to log the verification — appended to `docs/deployment-modes.md` with date + commit SHA + reviewer handle.

### SPEC-53.3 — Per-mode verification records ✅ (initial table populated 2026-04-25; graduations are continuous post-launch)

The matrix doc starts populated with what CI already verifies (SPEC-09) plus the modes for which we have working runbooks but no human-walkthrough yet. As maintainers walk through manual modes (typically at A8 rehearsal time and post-launch as customers report success), entries graduate from "documented but unverified" → "manually verified" with a dated record.

**Initial population at v0.1.0:**

CI-verified (via SPEC-09 release-smoke.yml):
- macOS arm64 + pipx (test-pypi)
- macOS x86_64 + pipx
- Ubuntu 22.04 x86_64 + pipx
- Ubuntu 24.04 arm64 + pipx
- Windows 2022 + pipx
- Ubuntu 22.04 x86_64 + Docker (ghcr.io)
- Ubuntu 22.04 x86_64 + Docker (Docker Hub)
- Ubuntu 24.04 arm64 + Docker (ghcr.io)
- Ubuntu 24.04 arm64 + Docker (Docker Hub)

Documented but unverified at v0.1.0 — graduate to manually-verified post-launch:
- GitLab CI (any host) — runbook in `docs/tutorials/ci-gitlab.md`
- CircleCI — runbook in `docs/tutorials/ci-circleci.md`
- Jenkins — runbook in `docs/tutorials/ci-jenkins.md`
- AWS EC2 commercial region + Bedrock backend — runbook in `docs/tutorials/deploy-govcloud-ec2.md` (commercial-region variant)
- AWS GovCloud EC2 + Bedrock GovCloud — runbook in `docs/tutorials/deploy-govcloud-ec2.md`; SPEC-13 smoke is the automated check once a maintainer has GovCloud creds
- Air-gap container — runbook stub in `docs/tutorials/deploy-air-gap.md`

## Roll-up exit criterion (gate A7)

- [ ] `docs/deployment-modes.md` exists with the table populated for v0.1.0 reality.
- [ ] `docs/manual-verification-runbook.md` exists with the template sections.
- [ ] Every mode listed as "documented but unverified" has a tutorial or pointer to the runbook used to walk it.
- [ ] At least the GovCloud-EC2 mode has a manual-verification record by the maintainer (this is the highest-stakes ICP-A path).

## Risks

- **The "documented but unverified" status is honest but unsatisfying.** Mitigation: each unverified mode names exactly what would close it (a runbook execution + a record entry). The status reads as a roadmap, not a deficiency.
- **Manual verification grows stale.** Mitigation: the matrix table includes commit SHA at verification time; if the verification SHA is more than 6 months behind main, the entry is auto-flagged "stale" via a CI check (follow-up).
- **Customer-reported verifications get filed differently from maintainer-walked ones.** Acceptable. The matrix accepts both, distinguishing reviewer handle when relevant.

## Open questions

- Should manual-verification records be GitHub Discussions (more accessible) or PRs editing the matrix doc (more durable)? Answer: PRs to the matrix doc. Discussions would scatter the signal.
- Should the matrix include a per-mode "last attempted but failed" entry? Answer: yes, for transparency. If someone tries air-gap and runs into a clear blocker, that's worth recording even unresolved.
