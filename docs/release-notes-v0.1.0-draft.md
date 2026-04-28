# Efterlev v0.1.0 — release notes (DRAFT)

> **DRAFT — not yet published.** This file is a scaffolded draft for the
> maintainer to edit before cutting `v0.1.0`. It captures the shipping
> state as of `main` immediately after the v1-readiness arc closed
> (2026-04-28). The maintainer should treat this as raw material — edit
> for tone, audience, and what to lead with — before posting to the
> GitHub Release page or blog.

---

## TL;DR

Efterlev v0.1.0 is the first public release: a local-first compliance scanner
for SaaS companies pursuing FedRAMP 20x Moderate. It reads your Terraform
(and `.github/workflows/`), produces evidence for the FedRAMP Key Security
Indicators it can see, and lets you drive a Claude-backed Gap, Documentation,
and Remediation Agent over that evidence — all without sending your code to a
SaaS, an account, or a procurement cycle. The detector library covers **30 of
60 thematic KSIs across 8 of 11 themes**, with **43 deterministic detectors**
producing content-addressed Evidence that the agents reason over and that 3PAOs
can verify. The 3 cross-cutting CSX KSIs (which AWS counts to arrive at the
"63 KSIs" framing in their [2026-04-27 deep-dive blog](https://aws.amazon.com/blogs/publicsector/deep-dive-into-fedramp-20x-key-security-indicators-decoding-the-63-ksis/))
are satisfied by Efterlev's existing pipeline outputs — see
[docs/csx-mapping.md](https://github.com/efterlev/efterlev/blob/main/docs/csx-mapping.md).
Pure OSS under Apache-2.0; no commercial tier, no managed SaaS, ever.

## Highlights

- **One command for the full pipeline** — `efterlev report run` orchestrates
  init → scan → Gap Agent → Documentation Agent → POA&M generation in one
  invocation. Add `--watch` to keep running and re-execute on file changes
  (debounced 2s).
- **Reports a 3PAO actually wants to read** — every HTML report opens with a
  coverage matrix (11 themes × 60 KSIs heatmap), filter pills + free-text
  search + sort controls, drill-down per classification, a print stylesheet
  that doesn't break across pages, and a JSON sidecar parallel to every HTML
  for downstream tooling.
- **Diff between scans for CI gating** — `efterlev report diff PRIOR CURRENT`
  produces a categorized HTML page (regressed first, then added, improved,
  shifted, removed, unchanged) and a JSON sidecar. Exits with code 2 if any
  KSI regressed since the prior scan — drop into a CI step to block PRs
  that worsen posture.
- **Friendly errors and `efterlev doctor`** — credential failures surface as
  one-line messages with remediation hints instead of 600-line SDK
  tracebacks. `efterlev doctor` runs five pre-flight checks (Python, .efterlev
  workspace, FRMR cache, ANTHROPIC_API_KEY shape, Bedrock credentials)
  with per-check pass/warn/fail.
- **Local-first, GovCloud-aware** — runs against either the Anthropic API or
  AWS Bedrock (FedRAMP-authorized, including GovCloud). Choose your backend
  at `efterlev init`; switch later with `efterlev init --force`.

## What's new in v0.1.0

This is the first public release, so "what's new" is everything. The
detail below is grouped by the v1-readiness-plan priorities the work
closed. See `CHANGELOG.md` for the per-PR breakdown.

### Detectors (43)

Every detector is self-contained under `src/efterlev/detectors/<source>/<capability>/`
with `detector.py`, `mapping.yaml`, `evidence.yaml`, `fixtures/`, and a
README that names what the detector proves and what it does NOT prove.

- **39 Terraform detectors** read `.tf` files (and `terraform show -json`
  output via `--plan` mode for module-composed codebases).
- **4 GitHub-workflows detectors** read `.github/workflows/*.yml` for
  CI-gating, supply-chain, and deployment-pattern KSIs that have no
  IaC analog.
- **30 of 60 KSIs covered across 8 of 11 themes** (CNA, CMT, IAM, MLA,
  PIY, RPL, SCR, SVC). The remaining 3 themes (AFR, CED, INR) are
  entirely procedural/governance and need Evidence Manifests (see
  below) rather than detector evidence.
- **7 supplementary 800-53-only detectors** carry `ksis=[]` because their
  underlying control (SC-28 for encryption-at-rest families; IA-5 for
  password policy; AC-3 for S3 public-access blocks) is not listed in
  any KSI's `controls` array in FRMR 0.9.43-beta. These surface in the
  gap report's "Unmapped findings" section — honest about the FRMR
  mapping gap, not invented attribution.

### HTML reports

The reports are self-contained: inline CSS, vanilla JS (no framework),
no external CDN, no fonts beyond system-default, no analytics. Every
file is portable, emailable, and archivable.

- Coverage matrix at the top of the gap report — 11 themes × 60 KSIs
  heatmap; click cells to scroll to the per-KSI classification card.
- Filter-by-status pills, free-text search box, sort controls (KSI /
  severity / evidence count). All compose freely.
- Per-classification drill-down listing each cited evidence's
  `detector_id` + `source_file:line_range`.
- Print stylesheet — interactive bits hide; cards don't split across
  pages.
- Diff view — `efterlev report diff PRIOR CURRENT` produces both
  `gap-diff-{ts}.html` and `gap-diff-{ts}.json`. Categorized:
  regressed first, then added, improved, shifted, removed, unchanged
  collapsed under `<details>`.
- JSON sidecar on every HTML report (gap, documentation, remediation).
  Schema-versioned. Suitable for tool integration.

### CLI / UX

- `efterlev report run` — one-command pipeline with per-stage
  `--skip-init` / `--skip-document` / `--skip-poam` flags. Add `--watch`
  for debounced re-run on `.tf` / `.tfvars` / `.yml` / `.yaml` / `.json`
  changes.
- `efterlev report diff PRIOR CURRENT` — gap-diff with HTML + JSON output.
- `efterlev doctor` — five pre-flight checks with remediation hints.
- Friendly errors at every API/credential boundary.
- First-run wizard at `efterlev init` for users without configured
  credentials.
- Documentation Agent emits per-KSI progress (`[12/60] KSI-SVC-SNT ✓`)
  to stderr.

### Provenance and reasoning

- Content-addressed (`sha256:`) Evidence, Claim, and ProvenanceRecord —
  every artifact is hash-derived from its content, so identical inputs
  produce identical IDs.
- SQLite index + content-addressed blob store + append-only JSONL
  receipt log under `.efterlev/`. `efterlev provenance show <record_id>`
  walks the chain.
- Three Anthropic-backed agents — Gap (Opus 4.7), Documentation
  (Sonnet 4.6), Remediation (Opus 4.7). Default models are tunable per
  agent; agents have their own prompt files at
  `src/efterlev/agents/*_prompt.md`.
- Evidence Manifests at `.efterlev/manifests/*.yml` carry customer-authored
  procedural attestations alongside detector evidence. KSIs in procedural
  themes (AFR, CED, INR) need these.

### Backends

- Anthropic API (default) — direct.
- AWS Bedrock — opt-in via `[bedrock]` install extra; container image
  bakes it in. Tested against `us.anthropic.claude-opus-4-7-v1:0` and
  the Sonnet equivalent. Works in GovCloud.

### Governance

- Apache-2.0. Pure OSS — no commercial tier, no paid layer, no
  managed SaaS, ever. See `DECISIONS.md`.
- BDFL today; technical steering committee at 10 sustained
  contributors. See `GOVERNANCE.md`.

## Stats

- 43 detectors (36 KSI-mapped + 7 supplementary 800-53-only)
- 30 of 60 KSIs covered across 8 of 11 themes
- 24 CLI commands
- ~960 unit tests passing; mypy strict / ruff check / ruff format
  clean across ~165 source files
- Plan-JSON-mode equivalence tests (one per detector) lock that HCL-mode
  and plan-mode produce identical evidence for the same configuration

## Breaking changes

None. This is the first public release.

## Known limitations

- **Module composition needs plan-JSON.** Detectors target raw
  `resource "aws_*"` declarations; module-consumer codebases (very
  common in real-world FedRAMP customers) need to run with
  `terraform plan -out plan.bin && terraform show -json plan.bin >
  plan.json && efterlev scan --plan plan.json` to surface evidence
  inside upstream modules. See `LIMITATIONS.md` and the Documentation
  Agent's runtime-warning prompts.
- **CloudFormation, CDK, Pulumi, Kubernetes** — not yet covered. The
  detector framework supports multiple `source` types; CloudFormation
  and CDK are next on the roadmap.
- **Live-cloud scanning** — scope-deferred to v1.5+. Today, Efterlev
  reads source files only.
- **OSCAL output** — deferred to v1.5+, gated on first
  OSCAL-Hub-consuming customer.
- **3 KSI themes (AFR, CED, INR) are procedural-only** and need
  Evidence Manifests rather than detector evidence. The framework is
  in place; specific manifest examples are minimal at v0.1.0.

## Upgrade notes

This is the first public release; no upgrade path applies. For
contributors and pre-1.0 testers running off `main`: every prior commit
hash was experimental; v0.1.0 is the first stable starting point.

## Acknowledgments

This release closes Priorities 1, 2, and 3 of `docs/v1-readiness-plan.md`
across 38 PRs landed 2026-04-27 → 2026-04-28. The detector breadth
target (30 KSIs / 8 themes) was reached at PR #51; the HTML overhaul
shipped across PRs #52–#62; the UX work shipped across PRs #64–#69.
Plan-doc updates and supporting docs (CHANGELOG, README refresh, docs
site refresh, multi-target dogfood validation) followed in PRs #63,
#70–#73.

Priority 4 (boundary scoping) shipped earlier. Priority 5 (real-customer
dogfood + 3PAO touchpoint) is calendar-time work that informs v0.1.x
patches and v0.2 planning. Priority 6 (honesty pass on `ksis=[]`
detectors) shipped earlier as well; the remaining 7 supplementary 800-53-only
detectors are upstream-FRMR-blocked at the KSI mapping layer (SC-28
specifically).

---

*Pronounced "EF-ter-lev." From Swedish efterlevnad (compliance).*
