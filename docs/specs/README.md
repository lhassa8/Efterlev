# Spec index

Efterlev is built spec-driven. Every non-trivial unit of work gets a single-page spec before implementation. The spec is the source of truth; the PR implements the spec; tests verify the spec holds.

This index lists every spec by ID, gate, size, and status.

## Why spec-driven, and how it composes with gate-driven launch

- **Gate-driven** (see `DECISIONS.md` 2026-04-23 "Rescind closed-source lock") answers *when* we advance between phases: exit criterion met → advance, never "it's Friday."
- **Spec-driven** answers *what* we build inside a gate: each item becomes a one-page spec; the spec is the source of truth; the PR implements the spec; tests verify the spec holds.

The two compose. Gate-driven is the outer loop (phase progression); spec-driven is the inner loop (how any single item gets built). Neither replaces the other.

## Status values

- `draft` — written but not yet review-approved
- `accepted` — reviewed and ready for implementation
- `implemented` — PR(s) merged; behavior matches spec
- `superseded` — replaced by a newer spec; link at the top of the superseded file

## Size estimates

- `S` — ≤1 day of focused work (one PR, usually)
- `M` — 2–5 days (one or a small series of PRs)
- `L` — ≥1 week (consider splitting; L specs should be rare)

Sizes are estimates, not commitments. Gate-driven means we don't pay calendar tax if a spec takes longer than estimated; we just finish it.

## Authoring workflow

1. Copy `TEMPLATE.md` to `SPEC-NN.md` where `NN` is the next unused number.
2. Fill in every section. If you can't write an Exit criterion, the spec isn't done.
3. Status: `draft` until reviewed; `accepted` once reviewed and ready to implement; `implemented` once the PR(s) land.
4. Keep the file under ~1 page. A spec that sprawls needs to be split into multiple specs.
5. Add an entry to this index under the appropriate gate section.

## Hybrid writing policy (2026-04-23)

Per the coding-plan pivot: gates A1 and A2 have full specs written upfront. Gates A3–A8 have one-line sketches in this index; each is fleshed into a full spec file as its gate approaches. This avoids pre-committing a month of spec-writing against specs the landscape may change before they land.

---

## A1 — Identity, governance, naming

Exit criterion for the gate: names squat-protected across every platform; `efterlev/` GitHub org owns the repo; `GOVERNANCE.md`, `CODE_OF_CONDUCT.md`, and the 2026-04-23 DECISIONS entry landed; signing policy written and enforced.

- [SPEC-01](SPEC-01.md) — Name squatting and canonical identity — S — partially implemented (PyPI + GitHub org + domains held; Docker Hub / npm / repo-transfer pending)
- [SPEC-02](SPEC-02.md) — GOVERNANCE.md — S — implemented
- [SPEC-03](SPEC-03.md) — CODE_OF_CONDUCT.md — S — implemented
- [SPEC-04](SPEC-04.md) — Commit-signing policy — S — docs landed (maintainer config actions pending post-repo-transfer)

## A2 — Distribution and install UX

Exit criterion: `pipx install efterlev` works from PyPI on macOS/Linux/Windows; `docker run ghcr.io/efterlev/efterlev` works on amd64 and arm64; `efterlev/scan-action@v1` works end-to-end in a throwaway test repo; every artifact is cryptographically verifiable.

- [SPEC-05](SPEC-05.md) — PyPI release pipeline (trusted publishing) — M — workflow landed (maintainer registrations + dry-run pending)
- [SPEC-06](SPEC-06.md) — Container image (multi-arch) — M — Dockerfile + workflow landed (Docker Hub token + dry-run pending)
- [SPEC-07](SPEC-07.md) — Composite GitHub Action (efterlev/scan-action) — M — pushed + protected (v1.0.0 tag gated on Efterlev v0.1.0 shipping)
- [SPEC-08](SPEC-08.md) — Sigstore signing + SLSA provenance — M — verify-release.sh + RELEASE.md landed (first-release dry-run pending)
- [SPEC-09](SPEC-09.md) — Install-verification CI smoke tests — M — workflow + fixture + assert.py landed (first-release dry-run pending)

## A3 — Bedrock backend

Exit criterion: `efterlev agent gap` completes end-to-end against Bedrock from an EC2 instance with only the Bedrock VPC endpoint reachable. The GovCloud deploy doc has been walked by someone other than the author and found correct.

- [SPEC-10](SPEC-10.md) — AnthropicBedrockClient — M — implemented (real-Bedrock acceptance owned by SPEC-13)
- [SPEC-11](SPEC-11.md) — `LLMConfig.backend`/`region` config surface — S — implemented
- [SPEC-12](SPEC-12.md) — GovCloud deploy tutorial — S — tutorial landed (real-instance walkthrough pending)
- [SPEC-13](SPEC-13.md) — Bedrock smoke test in e2e harness — S — implemented (real-Bedrock run pending maintainer creds)

## A4 — Detector breadth to 30

Exit criterion: 30 detectors total (14 existing + 16 new), all passing the full test matrix (unit + integration + HCL/plan-JSON equivalence). Coverage of 9 of 11 KSI themes with at least one detector contribution.

[SPEC-14](SPEC-14.md) is an omnibus spec covering all 16 new detectors. The detector contract is shared (detector.py + mapping.yaml + evidence.yaml + fixtures/ + README.md), so per-detector content is compact. SPEC-14 documents the shared parts once and gives each of the 16 detectors a focused mini-section (signal, resource types, KSI/control mapping, what-it-proves, what-it-doesn't, fixture plan, edge cases).

- [SPEC-14](SPEC-14.md) — A4 omnibus: 16 detectors to reach 30 — L (S each) — implemented (16/16 landed; gate A4 closed)

The 16 detectors covered in SPEC-14:

| Sub-spec | Detector | Family / 800-53 |
|---|---|---|
| 14.1 | `aws.security_group_open_ingress` | SC-7 |
| 14.2 | `aws.rds_public_accessibility` | SC-7 / AC-3 |
| 14.3 | `aws.s3_bucket_public_acl` | SC-7 / AC-3 |
| 14.4 | `aws.nacl_open_egress` | SC-7 |
| 14.5 | `aws.cloudwatch_alarms_critical` | SI-4(2,4) / AU-6 |
| 14.6 | `aws.guardduty_enabled` | SI-4 / RA-5 |
| 14.7 | `aws.config_enabled` | CM-2 / CM-8 |
| 14.8 | `aws.access_analyzer_enabled` | CA-7 / AC-6 |
| 14.9 | `aws.kms_customer_managed_keys` | SC-12 |
| 14.10 | `aws.secrets_manager_rotation` | SC-12 / IA-5(1) |
| 14.11 | `aws.sns_topic_encryption` | SC-28 |
| 14.12 | `aws.sqs_queue_encryption` | SC-28 |
| 14.13 | `aws.iam_inline_policies_audit` | AC-6 / AC-2 |
| 14.14 | `aws.iam_admin_policy_usage` | AC-6(2) |
| 14.15 | `aws.iam_service_account_keys_age` | IA-2 / IA-5 |
| 14.16 | `aws.elb_access_logs` | AU-2 / AU-12 |

## A5 — Trust surface

Exit criterion: a hypothetical hostile security reviewer with two hours to spend cannot find a trust gap that isn't already named in one of these docs.

[SPEC-30](SPEC-30.md) is an A5 omnibus consolidating the 8 trust-surface deliverables into one spec with per-deliverable sub-sections. Same pattern as SPEC-14 — the deliverables share a coherent goal (convince a hostile reviewer the surface is well-tended) but ship as different artifact types (Markdown policies, GitHub templates, CI workflows, branch-protection config, a pre-launch review record).

- [SPEC-30](SPEC-30.md) — A5 omnibus: 8 trust-surface deliverables — L (S/M each) — mostly implemented (7/8 landed; branch-protection enforcement + reviewer sign-off + GitHub-only smoke checks are maintainer actions at A8)

The 8 sub-deliverables in SPEC-30:

| Sub-spec | Deliverable | Type |
|---|---|---|
| 30.1 | `SECURITY.md` + coordinated-disclosure process | Markdown |
| 30.2 | `THREAT_MODEL.md` public-repo refresh | Markdown |
| 30.3 | Issue templates (bug, detector-proposal, doc) | GitHub config |
| 30.4 | PR template + checklist | GitHub config |
| 30.5 | Branch protection enforcement | repo settings (cross-refs SPEC-04) |
| 30.6 | Dependabot config | YAML |
| 30.7 | CI security scanning (pip-audit, bandit, semgrep, CodeQL) | GitHub workflow |
| 30.8 | Pre-launch security review record | Markdown attestation |

## A6 — Documentation site

Exit criterion: a naive reader can go from the home page to "I've run `efterlev scan` on a sample repo" in under 5 minutes, measured on three readers who haven't seen the project before.

[SPEC-38](SPEC-38.md) is an A6 omnibus consolidating the 15 docs-site deliverables. Same pattern as SPEC-14 / SPEC-30 — shared MkDocs theme/build/deploy contract, per-page exit criteria.

- [SPEC-38](SPEC-38.md) — A6 omnibus: MkDocs site + 15 content pages — L (S/M each) — partially implemented (scaffold + home + quickstart + key concepts + FAQ + comparisons + reference stubs landed; remaining pages stubbed; auto-gen reference + tutorial deepening queued)

The 15 sub-deliverables in SPEC-38:

| Sub-spec | Deliverable | Status |
|---|---|---|
| 38.1 | MkDocs scaffold + theme + deploy | landed (mkdocs.yml, [docs] extra, docs-deploy.yml, CNAME) |
| 38.2 | Home page | landed (full content) |
| 38.3 | Quickstart | landed (full content) |
| 38.4 | Concept pages (4) | KSIs-for-engineers landed; 3 stubbed |
| 38.5 | Install tutorial | stubbed |
| 38.6 | CI integration tutorials (4) | GitHub Actions landed; 3 stubbed |
| 38.7 | GovCloud deploy tutorial | landed (lifted from SPEC-12) |
| 38.8 | Air-gap deploy tutorial | stubbed |
| 38.9 | Write-a-detector tutorial | stubbed |
| 38.10 | Write-a-manifest tutorial | stubbed |
| 38.11 | Customize-agent-prompt tutorial | stubbed |
| 38.12 | Comparison pages (5) | Paramify landed; 4 stubbed |
| 38.13 | Auto-generated reference (6) | stubs in place; auto-gen queued |
| 38.14 | Architecture overview | landed (existing doc cross-linked) |
| 38.15 | FAQ | landed (full content) |

## A7 — Deployment-mode verification matrix

Exit criterion: every CI-labeled mode passes on the release-candidate build; every Manual-labeled mode has a written, reproducible procedure and a dated "last verified" stamp.

[SPEC-53](SPEC-53.md) is an A7 omnibus consolidating the 3 sub-deliverables. Significant overlap with SPEC-09 (release-smoke matrix) — SPEC-53 records what's CI-covered vs what needs manual walking, plus the runbook template for the manual modes.

- [SPEC-53](SPEC-53.md) — A7 omnibus: deployment-mode matrix + manual-verification runbook + per-mode records — M — implemented (matrix doc + runbook landed; per-mode walkthroughs are continuous post-launch work)

The 3 sub-deliverables in SPEC-53:

| Sub-spec | Deliverable | Status |
|---|---|---|
| 53.1 | Deployment-mode matrix doc (`docs/deployment-modes.md`) | landed — 9 CI-verified modes, 6 documented-but-unverified modes |
| 53.2 | Manual-verification runbook template (`docs/manual-verification-runbook.md`) | landed |
| 53.3 | Per-mode verification records | initial table populated; graduations from ⚪ → 🟡 happen as maintainers + customers walk modes |

## A8 — Launch rehearsal

Exit criterion: a maintainer other than the author runs the launch checklist end-to-end in a staging fork and reports zero surprises.

[SPEC-56](SPEC-56.md) is an A8 omnibus consolidating the 5 launch-rehearsal artifacts. Same omnibus pattern as SPEC-14 / SPEC-30 / SPEC-38 / SPEC-53.

- [SPEC-56](SPEC-56.md) — A8 omnibus: pre-flip grep-scrub + launch runbook + failure-response + announcement copy + design-partner outreach — M — implemented (`launch-grep-scrub.sh` exits clean as of 2026-04-25; rehearsal walkthrough + maintainer-action queues are the closing actions before public flip)

The 5 sub-deliverables in SPEC-56:

| Sub-spec | Deliverable | Status |
|---|---|---|
| 56.1 | Pre-flip grep/scrub checklist + script | landed (`scripts/launch-grep-scrub.sh` + `.allowlist` + `docs/launch/grep-scrub-checklist.md`) |
| 56.2 | Launch runbook | landed (`docs/launch/runbook.md`) |
| 56.3 | Failure-response playbook | landed (`docs/launch/failure-response.md`) |
| 56.4 | Announcement copy | landed (`docs/launch/announcement-copy.md`) |
| 56.5 | Design-partner outreach templates | landed (`docs/launch/design-partner-outreach.md`) |

---

## Post-launch (Phase C) — not yet indexed

Phase C specs (Drift Agent, real PR creation, non-AWS detectors, first-user feedback window, workflow maturity Phase 5, community infrastructure, quality hardening) are written just-in-time once their gate approaches. The coding-plan hybrid explicitly defers these to keep planning capacity aligned with what's actually next.

## Superseded and historical specs

None yet.
