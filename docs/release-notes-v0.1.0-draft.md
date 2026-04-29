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
(and `.github/workflows/`) and produces KSI-classified evidence + a
3PAO-shaped attestation summary — locally, without sending your code to a
SaaS or going through a procurement cycle. Coverage at v0.1.0: **31 of 60
thematic KSIs across 8 of 11 themes**, **45 deterministic detectors**, three
Anthropic-backed agents (Gap, Documentation, Remediation). Apache-2.0; no
commercial tier, no managed SaaS at this time.

## Try it in 5 minutes

```bash
pipx install efterlev
cd path/to/your/terraform
efterlev init                     # ~10 seconds
export ANTHROPIC_API_KEY=sk-ant-…  # or configure AWS Bedrock at init
efterlev report run               # full pipeline; writes HTML report + JSON sidecar to .efterlev/reports/
```

On a typical SaaS Terraform repo of ~30–50 resources, the deterministic
stages complete in seconds; the Gap Agent runs in roughly a minute on
Opus 4.7; the Documentation Agent's per-KSI narrative pass runs ~30-60s/KSI
on Sonnet 4.6, so a full baseline of ~60 KSIs typically completes in
**30 minutes to an hour on first run**. Use `--skip-document` (just Gap +
POA&M) for a faster ~5-minute iteration loop while you patch findings;
re-run with the Documentation stage included before the 3PAO hand-off.

If you don't have ANTHROPIC_API_KEY or Bedrock configured, run
`efterlev scan` (the deterministic stage) by itself first — it
produces evidence + an HTML coverage view with no LLM call.

## Highlights

- **One command for the full pipeline** — `efterlev report run` orchestrates
  init → scan → Gap Agent → Documentation Agent → POA&M generation in one
  invocation. Add `--watch` to keep running and re-execute on file changes
  (debounced 2s).
- **Reports designed for 3PAO review** — every HTML report opens with a
  coverage matrix (11 themes × 60 KSIs heatmap), filter pills + free-text
  search + sort controls, drill-down per classification, a print stylesheet
  that doesn't break across pages, and a JSON sidecar parallel to every HTML
  for downstream tooling. (Empirical 3PAO acceptance is being validated in
  v0.1.x — see Priority 5 of `docs/v1-readiness-plan.md`.)
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
- **CSX-SUM cadence inline** — the Documentation Agent's
  `documentation-{ts}.json` artifact carries per-KSI
  `machine_validation_cadence` and `non_machine_validation_cadence`
  fields stamped from the workspace's `[cadence]` config. Customers
  running the drop-in `pr-compliance-scan.yml` GitHub Action get the
  canonical values for free; non-standard pipelines edit
  `.efterlev/config.toml` once. The cadence flows inline with the
  rest of each KSI's evidence — a 3PAO ingesting the JSON sidecar
  reads the persistent cycle alongside the citations rather than
  chasing it through CI configuration.
- **CSX-ORD prescribed-sequence sort** — `efterlev poam --sort csx-ord`
  orders POA&M items by the FRMR catalog's prescribed initial-
  authorization KSI sequence (MAS, ADS, UCM, …); the default
  `--sort severity` keeps developer-prioritized triage output. Both
  modes are honest; neither pretends to be the other.
- **Catalog freshness warnings at init time** — `efterlev init` emits
  non-blocking warnings if the vendored FRMR catalog is more than
  180 days past its `last_updated` date, or if today is past the
  announced CR26 release window (2026-06-30) with a beta-version
  catalog. Init still proceeds; the warnings flag "you may be running
  a stale Efterlev" before the customer commits to a posture report.
- **Local-first, GovCloud-compatible** — runs against either the Anthropic API or
  AWS Bedrock. The Bedrock backend has been tested against
  `us.anthropic.claude-opus-4-7-v1:0` and the Sonnet equivalent in commercial
  regions; GovCloud (`us-gov-west-1`, `us-gov-east-1`) is a supported configuration
  but a full first-party walkthrough has not yet been performed end-to-end —
  that's tracked alongside Priority 5. Choose your backend at `efterlev init`;
  switch later with `efterlev init --force`.

## What's new in v0.1.0

This is the first public release, so "what's new" is everything. The
detail below is grouped by the v1-readiness-plan priorities the work
closed. See `CHANGELOG.md` for the per-PR breakdown.

### Detectors (45)

Every detector is self-contained under `src/efterlev/detectors/<source>/<capability>/`
with `detector.py`, `mapping.yaml`, `evidence.yaml`, `fixtures/`, and a
README that names what the detector proves and what it does NOT prove.

- **41 Terraform detectors** read `.tf` files (and `terraform show -json`
  output via `--plan` mode for module-composed codebases).
- **4 GitHub-workflows detectors** read `.github/workflows/*.yml` for
  CI-gating, supply-chain, and deployment-pattern KSIs that have no
  IaC analog.
- **31 of 60 KSIs covered across 8 of 11 themes** (CNA, CMT, IAM, MLA,
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
  the Sonnet equivalent in commercial regions. GovCloud
  (`us-gov-west-1`, `us-gov-east-1`) is a supported configuration; a
  full first-party walkthrough is tracked alongside Priority 5.

### Governance

- Apache-2.0. Pure OSS — no commercial tier, no paid layer, no
  managed SaaS at this time. See `DECISIONS.md`.
- BDFL today; technical steering committee at 10 sustained
  contributors. See `GOVERNANCE.md`.

## Stats

- 45 detectors (38 KSI-mapped + 7 supplementary 800-53-only)
- 31 of 60 KSIs covered across 8 of 11 themes
- 24 CLI commands
- ~1,015 unit tests passing; mypy strict / ruff check / ruff format
  clean across ~170 source files
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
- **AWS-only at the IaC layer today.** Of the 38 KSI-mapped detectors,
  34 read AWS-resource-shaped Terraform (`aws_*` resources); 4 read
  `.github/workflows/`. An Azure-only or GCP-only customer running
  `efterlev scan` against their Terraform gets near-zero KSI evidence.
  CloudFormation, CDK, Pulumi, k8s, Azure ARM, and GCP DM detector
  sources are on the v1.5+ roadmap; the detector framework already
  supports multiple `source` types, so each is detector-implementation
  work, not framework work.
- **Live-cloud scanning** — scope-deferred to v1.5+. Today, Efterlev
  reads source files only.
- **OSCAL output** — deferred to v1.5+, gated on first
  OSCAL-Hub-consuming customer.
- **3 KSI themes (AFR, CED, INR) are procedural-only** and need
  Evidence Manifests rather than detector evidence. The framework is
  in place; specific manifest examples are minimal at v0.1.0.
- **Empirical 3PAO acceptance** of the CSX-SUM-shaped attestation
  artifact is gated on Priority 5 of `docs/v1-readiness-plan.md`
  (real-customer dogfood + 3PAO touchpoint). Until that closes,
  the artifact is "shaped to satisfy CSX-SUM," not validated as
  "the artifact 3PAOs accept."

## Upgrade notes

This is the first public release; no upgrade path applies. For
contributors and pre-1.0 testers running off `main`: every prior commit
hash was experimental; v0.1.0 is the first stable starting point.

## Acknowledgments

v0.1.0 is a milestone release of an OSS project built in the open against
a moving FedRAMP 20x catalog. The shape was driven by watching SaaS
founders bounce off Authorization-to-Operate work because the existing
tooling — auditor-facing GRC platforms, runtime drift detectors —
assumed an established compliance team. Efterlev is for the team that
*doesn't have one yet* and needs to know where they stand before they
provision anything. The CHANGELOG carries the per-PR detail for contributors
who want it.

Open issues we know about: Priority 5 (real-customer dogfood + 3PAO
touchpoint) is the largest open thread and the most important next signal —
empirical 3PAO acceptance of the CSX-SUM-shaped artifact will tell us
whether the design choices in v0.1.0 hold up under assessment workflow.
Priority 4 (boundary scoping) shipped earlier in the v0 arc. The 7
supplementary 800-53-only detectors marked `ksis=[]` (SC-28 family
mostly) reflect a real upstream FRMR mapping gap rather than missing
work; that gap is being raised upstream.

If you're a SaaS founder or compliance lead testing v0.1.0 against a real
Terraform tree, the maintainer wants to hear what you found — open an issue
or send a PR with a redacted Terraform fixture.

---

*Pronounced "EF-ter-lev." From Swedish efterlevnad (compliance).*
