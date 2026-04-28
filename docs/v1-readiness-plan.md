# Efterlev v1 readiness plan

**Status:** active. Authored 2026-04-27 after maintainer's strategic-reset call.
**Tracking:** this document is the durable plan for what "outstanding v1" means and what work that requires. Each priority links to the work that lands it. The launch tag (v0.1.0) does not get cut until every priority is complete and the validation gate (§7) clears.

---

## The strategic reset

The pre-2026-04-27 plan was: close the readiness gates, sign off on the security review, tag v0.1.0, flip the repo public, and post the launch announcement. The maintainer rescinded that plan on 2026-04-27 with the framing:

> "I don't want the first release to be 'interesting and potentially helpful'. I want it to be outstanding. The core must be strong and comprehensive."

This document captures what "outstanding" means, the seven concrete priorities required to get there (six original + one added 2026-04-27 from a real-codebase dogfood pass), and what is deliberately deferred. Until every priority below clears its acceptance gate, the launch tag does not get cut. There is no calendar deadline; there is a quality bar.

The DECISIONS.md entry for this reset is dated 2026-04-27 ("Strategic reset — raise v1 bar"); see there for the alternatives considered.

---

## What "outstanding" means for ICP-A

The target user is a VP Eng or DevSecOps lead at a SaaS company pursuing first FedRAMP Moderate. "Remarkable" to them is not "more features." It is:

1. **They ran one command and got an answer they trust.** Not a partial answer with caveats they have to internalize.
2. **The answer was specific enough to act on Monday morning.** Concrete weaknesses, concrete remediations, citations they can show their team.
3. **The output looks like something they would be proud to email to their 3PAO.** Not a draft hand-off — an artifact.
4. **It worked on real codebases.** Not toy fixtures, not the maintainer's dogfood.

Every priority below ladders up to one or more of those four.

---

## The seven priorities

> **Sequencing note (added 2026-04-27 from dogfood):** Priority 0 was added after a real-codebase dogfood pass against `aws-ia/terraform-aws-eks-blueprints/patterns/blue-green-upgrade` showed that 30 detectors fire just 1× against the dominant ICP-A Terraform pattern (module composition). Without addressing module expansion, every subsequent detector built under priority 1 would fire zero against module-composed codebases, burning weeks of work on no signal. Priority 0 must land before priority 1; the rest of the priorities follow as originally sequenced. See `docs/dogfood-findings-2026-04-27.md` for the full rationale.

### 0. Module-expansion handling and plan-JSON discoverability

**Today:** Efterlev's detectors look for raw `resource "aws_*"` declarations. The dominant ICP-A Terraform pattern is module composition (`module "eks" { source = "terraform-aws-modules/eks/aws" ... }`). All the real workload — EKS cluster, VPC, IAM roles, KMS keys, security groups, CloudTrail — lives inside upstream modules that Efterlev never sees in HCL mode. Plan-JSON mode (`efterlev scan --plan plan.json`) IS the documented workaround, but it lives in `LIMITATIONS.md`, not the README quickstart, and requires `terraform plan` against AWS — a heavy ask for a first-time user.

**Target:** a first-time ICP-A user running `efterlev scan` against a module-composed codebase gets a clear, actionable signal that they should re-run with plan-JSON for full coverage. The HCL-mode result is honest about its coverage limitations. Plan-JSON discoverability is in the README, not buried in LIMITATIONS.

**Acceptance criteria:**
- **Module-call density warning at scan time:** when `efterlev scan` (HCL mode) parses a target where `module_calls > resources` or `module_calls >= 3`, emit a structured warning to stdout: `N module calls detected; detector coverage will be limited without plan-JSON expansion. Run \`terraform init && terraform plan -out plan.bin && terraform show -json plan.bin > plan.json && efterlev scan --plan plan.json\` for full coverage.` Exit code stays 0 (the scan succeeded). The warning surfaces in the eventual JSON sidecar (priority 2) as a structured `warnings` array.
- **README quickstart presents both paths:** "module-composed (most ICP-A codebases): use plan-JSON" and "raw resources: HCL mode works directly." The dominant path becomes the primary path. Cross-reference where to find more detail.
- **Documentation Agent narratives reflect coverage:** when the underlying scan was thin-evidence due to module composition, the agent's narratives explicitly note "this scan was HCL-mode against a module-composed codebase; plan-JSON would surface more evidence." Today's narratives are honest but generic; this makes them honest AND specific.
- **Re-run dogfood:** against the same `aws-ia/terraform-aws-eks-blueprints/patterns/blue-green-upgrade` SHA, the pipeline produces ≥10 evidence records (vs today's 1) when run with plan-JSON, OR emits a clear warning + actionable remediation when run without.
- **Optional `--auto-plan` flag** that runs `terraform init && terraform plan` for the user (with explicit opt-in and credentials prompt). Stretch; defer if other Priority 0 work runs long.

**Effort estimate:** 1.5–2 weeks. Module-call detection in the existing parser is small (~1 day); the warning surface, README rewrite, and Documentation Agent metadata wiring are each ~2 days. The optional `--auto-plan` flag with credentials handling is the most substantial stretch piece.

**Deliberately excluded:** automatic `terraform plan` execution as the default behavior. That is too magic and crosses too many trust boundaries (running tools against the user's AWS account). Plan-JSON as an explicit user choice with clear instructions is the right v1 shape.

**Why this is priority 0, not priority 7:** the dogfood made this concrete. A customer running Efterlev against their real codebase needs to see actual evidence, not 30 detectors firing zero against an EKS deployment. Without this, priorities 1–6 stand on a foundation that produces "1 evidence record" against real codebases — and adding 18 new detectors under priority 1 just makes it "1 evidence record from 48 detectors."

---

### 1. Detector breadth to ≥30 KSI coverage at the repo-evidenceable layer ✅ FLOOR REACHED 2026-04-27

**Today (2026-04-27, post-PR #51):** **30 of 60 KSIs** evidenced; **8 of 11 themes** covered (CNA, CMT, IAM, MLA, PIY, RPL, SCR, SVC). 7 of 43 detectors carry `ksis=[]` (the 7 supplementary 800-53-only detectors after Priority 6's honesty-pass rehoming). The remaining 3 themes (AFR, CED, INR) are entirely procedural/governance and require Evidence Manifests rather than detector evidence.

**Original starting state (2026-04-27):** 14 of 60 KSIs evidenced; 5 of 11 themes covered. 8 of 30 detectors carried `ksis=[]`.

**How we got here:** 11 priority-1.x PRs landed (1.2 → 1.16) — 13 fresh detectors + 3 cross-maps. See PR #51's body for the full table.

**Target:** 30+ of 60 KSIs evidenced; ≥8 of 11 themes covered. The IaC-evidenceable detectors we do not have but could (non-exhaustive):
- **CNA** (4 missing): DFP (defining functionality and privileges), IBP (best practices), OFA (optimizing for availability), ULN (using logical networking).
- **IAM** (4 missing): AAM (automating account management), APM (passwordless methods, configurable), JIT-config (just-in-time auth scaffolding), SUS-config (suspicious-activity response config).
- **MLA** (1 missing): ALA (authorizing log access — IAM policies on log buckets/streams).
- **SVC** (3 missing): PRR (preventing residual risk), RUD (removing unwanted data — lifecycle policies), VCM (validating communications — mTLS/cert validation).
- **CMT (currently 0 detectors)** (3 evidenceable from repo metadata): LMC (logging changes — read `.github/workflows/`, GitHub branch protection, PR-required-checks), RMV (redeploying vs modifying — read CI deploy patterns), VTD (validating throughout deployment — read CI gating).
- **SCR (currently 0 detectors)** (2 evidenceable from repo metadata): MIT (supply chain mitigation — read `dependabot.yml`, SLSA attestation config), MON (supply chain monitoring — read SBOM generation, CVE-scan config).
- **PIY (currently 0 detectors)** (1 evidenceable): GIV (generating inventories — read `terraform.tfstate` or plan JSON as authoritative inventory).

That is 18 candidate detectors. Land them and we go from 14 KSIs to 32 KSIs (counting some that share themes) and from 5 themes to 8 themes. A handful of the candidates above are speculative and may not work cleanly; the floor target is **30 KSIs across 8 themes**.

**Acceptance criteria — all met as of PR #51 (2026-04-27):**
- ✅ `efterlev detectors list` reports ≥30 KSIs evidenced across ≥8 themes (30 / 8).
- ✅ Every new detector follows the existing contract (detector.py + mapping.yaml + evidence.yaml + fixtures/ + README.md).
- ✅ Every new detector has unit tests (decorator round-trip + per-fixture).
- ✅ README's "what we cover" claim updates honestly to match the new number.
- ✅ Dogfood (`scripts/dogfood-real-codebases.sh`) `EXPECTED_DETECTOR_COUNT` updated each PR (currently 43).

**Effort actually taken:** approximately 1 day of focused detector work (the original 4-8 week estimate assumed sequential, individual-PR cadence). The 11 PRs landed in a single day's working session because the detector contract is small and well-shaped.

**Original deliberately-included (now done):** the un-attempted CMT/SCR/PIY repo-meta detectors landed cleanly: github.ci_validation_gates (CMT-VTD), github.supply_chain_monitoring (SCR-MON), github.action_pinning (SCR-MIT), github.immutable_deploy_patterns (CMT-RMV), aws.terraform_inventory (PIY-GIV). Repo metadata IS infrastructure-as-code in the broad sense; the original concern that these themes were "procedural-only" turned out to be wrong.

**Deliberately excluded (still excluded):** the 7 `ksis=[]` detectors remain supplementary 800-53-only contributions; the SC-28 cluster is upstream-FRMR-blocked per Priority 6's honesty pass.

**What's beyond the floor:** opportunities to push past 30 KSIs exist (e.g., MLA-ALA via log-bucket policies; CNA-OFA via availability-zone diversity). These are deferred unless customer feedback flags a specific gap.

---

### 2. Output HTML overhaul — beautiful, searchable, sortable, machine-readable

**Today:** HTML reports under `.efterlev/reports/` with inline CSS, no JavaScript, evidence-vs-claim color-coded cards. Functional. Emailable. Printable. Not remarkable.

**Target:** the report a 3PAO opens and immediately wants to read.

**Acceptance criteria:**
- **Coverage matrix at the top** — single-page heatmap of all 11 themes × all 60 KSIs, color-coded by status (`implemented` / `partial` / `not_implemented` / `evidence_layer_inapplicable` / `not_applicable`). One glance, full posture.
- **Search box** that filters cards by free text (KSI ID, control, theme, detector, content keyword).
- **Sort controls** by severity, KSI, control, source file, status, date.
- **Filter by status** — single click to "show me only `not_implemented`" for actionable focus.
- **Drill-down** — click an evidence card to see (a) the full source-file lines in context (with line-number anchors), (b) the LLM prompt that produced the claim (redacted by scrubber), (c) the cited evidence chain.
- **Diff view** — `efterlev report --compare-to .efterlev/reports/<prior-ts>.html` produces a diff page highlighting NEW findings, RESOLVED findings, and CHANGED status.
- **Machine-readable JSON sidecar** — every HTML report has a `.json` companion with the same data, schema-versioned, suitable for tool integration.
- **Print stylesheet** — interactive bits hide; cards flow cleanly on paper.
- **Self-contained** — no external CDN, no fonts beyond system-default, no analytics. Single HTML file plus the JSON sidecar.
- **No framework** — vanilla JS with progressive enhancement. The page must remain readable with JavaScript disabled (filter/sort gracefully degrade to "all results visible, sorted by KSI").

**Effort estimate:** 1–2 weeks for a strong overhaul, assuming we add about 1500 lines of vanilla JS and a few hundred lines of CSS.

**Deliberately excluded:** server-rendered comparison portals, hosted-search backends, anything that requires the user to deploy infrastructure. The HTML must remain a single self-contained file.

---

### 3. UX during install and usage — first-run-to-output is one command, with progress

**Today:**
- 5-command happy path: `init → scan → agent gap → agent document → poam`. Each is a separate user invocation.
- The 7-minute Documentation Agent run produces zero stdout until completion. People will think it hung.
- No `efterlev doctor` to self-diagnose `ANTHROPIC_API_KEY`, AWS creds, network reachability.
- No `--watch` mode.
- Errors on missing API key surface as `Error code: 401 - {'type': 'error', ...}` Anthropic SDK errors, not actionable.

**Target:** a first-time user runs one command and gets a complete, polished output, with informative progress along the way and helpful errors on failure.

**Acceptance criteria:**
- **One-command full pipeline:** `efterlev report` runs `init → scan → agent gap → agent document → poam` in sequence with a single progress UI. Existing per-stage commands remain (for power users and CI integration).
- **Progress indicators:** every long-running stage prints a structured progress line per unit (`[12/60] KSI-SVC-SNT ✓` for Documentation Agent; `[7/30] aws.encryption_s3_at_rest` for scan). When stdout is a TTY, progress lines update in place; when piped, they print one per line.
- **`efterlev doctor`** subcommand: checks Python version, `uv`/`pipx` install, `ANTHROPIC_API_KEY` presence and shape, optional AWS Bedrock creds reachability, network reachability to anthropic.com, FRMR catalog cache freshness. Reports per-check pass/fail with remediation suggestions ("Set `ANTHROPIC_API_KEY` — see https://console.anthropic.com").
- **`efterlev report --watch`:** re-runs scan + gap + document on file changes under `--target`, debounced to 2 seconds, with re-rendering only the changed KSI cards in HTML output.
- **Friendly errors** at every API/credential boundary: instead of raw SDK error JSON, emit one-sentence explanations + a remediation pointer.
- **First-run wizard:** on `efterlev init` in a directory without `.efterlev/`, if no API key is configured anywhere, offer an interactive prompt with documentation links instead of silently configuring something that will fail at first agent invocation.

**Effort estimate:** 1–1.5 weeks. Most pieces are small individually; the integration polish is what takes the time.

**Deliberately excluded:** a TUI dashboard. Curses-based interactive review. Those add framework dependencies and are not where ICP-A wants to spend their attention.

---

### 4. Authorization-boundary scoping

**Today:** Efterlev scans whatever directory `--target` points at. There is no concept of "in-scope vs. out-of-scope" within a codebase. A FedRAMP customer typically has their GovCloud workload Terraform alongside their commercial-side Terraform; today, Efterlev would mix evidence across both, producing a posture statement that is meaningless to a 3PAO.

**Target:** the customer can declare "boundary/** is in scope; everything else is out" and Efterlev's evidence, claims, POA&M, and HTML output all respect that boundary.

**Acceptance criteria:**
- **Boundary declaration** — `efterlev boundary set 'boundary/**' 'modules/in-scope-*/**'`, persisted to `.efterlev/config.toml` as a list of glob patterns. Both `--include` and `--exclude` supported.
- **Boundary on Evidence** — every `Evidence` record carries a `boundary_state` field: `in_boundary`, `out_of_boundary`, or `boundary_undeclared`. The detector populates it based on the source file's match against the boundary patterns.
- **Boundary on Claim** — Claims inherit boundary state from their cited evidence; a Claim citing only `out_of_boundary` evidence is itself flagged.
- **Default behavior** — without an explicit boundary declaration, the workspace state is `boundary_undeclared`. That means "we don't know your scope; we'll show all findings, but we can't tell a 3PAO this is your boundary."
- **HTML output** — `out_of_boundary` evidence cards collapse by default with an "out of declared boundary" badge; `boundary_undeclared` cards show a banner explaining the customer should declare scope for an honest posture statement.
- **POA&M** — only `in_boundary` and `boundary_undeclared` evidence becomes POA&M items. `out_of_boundary` does not.
- **CLI verbs** — `efterlev boundary show` (list current rules), `efterlev boundary check <path>` (test whether a file is in/out).

**Effort estimate:** 1.5 weeks. The data-model change touches Evidence, Claim, the store, every detector, every agent prompt, and the HTML renderer. Touching everything is the hard part.

**Deliberately excluded:** AWS-account-level boundary scoping (live cloud state would be required). For v1 the boundary is repo-relative; live-state correlation is post-v1.

---

### 5. One real-customer dogfood + one 3PAO touchpoint

**Today:** Efterlev has been dogfooded by the maintainer against `terraform-aws-modules` repos and the smoke fixture. No external party has used Efterlev end-to-end on a real codebase they cared about.

**Target:** at least one real ICP-A-shaped engagement, with the findings cataloged honestly. At least one real 3PAO (or compliance lead at a FedRAMP-authorized SaaS) has read an Efterlev attestation artifact and given substantive feedback.

**Acceptance criteria:**
- **Customer dogfood:** one design-partner-class engagement — a real SaaS company pursuing FedRAMP Moderate, who runs the full Efterlev pipeline on their actual Terraform, captures their experience in writing, and identifies specific points where the tool helped or fell short. Result captured in `docs/dogfood-customer-<name>-<YYYY-MM-DD>.md`.
- **3PAO touchpoint:** at least one real 3PAO conversation, with the Efterlev attestation artifact in hand. Their feedback captured in `docs/3pao-feedback-<name>-<YYYY-MM-DD>.md` with their specific verdict on whether they would accept the artifact as one input to their FedRAMP review, and what they would change before accepting it.
- **No quoting without permission.** Both records have explicit consent from the named party before being committed. Fall-back: anonymized version with the consent scope (e.g., "anonymous senior 3PAO at a major audit firm").

**Effort estimate:** calendar-time, not engineering-time. 4–8 weeks to find, schedule, and capture results from each. Outreach uses `docs/launch/design-partner-outreach.md` as the starting point; that doc was written for v0.1.0 launch and applies here equally.

**Why this is on the priority list and not the followup list:** every other priority above is engineering work that improves the artifact. This priority is the only one that validates the artifact actually does what it claims for someone who is not the maintainer. Without it, we are shipping an unproven tool no matter how polished the engineering.

---

### 6. Honesty pass on the 8 `ksis=[]` detectors

**Today:** 8 of 30 detectors (`encryption_ebs`, `iam_password_policy`, `kms_key_rotation`, `encryption_s3_at_rest`, `s3_public_access_block`, `sqs_queue_encryption`, `sns_topic_encryption`, `rds_encryption_at_rest`) carry `ksis=[]` because their controls (SC-28, SC-12, AC-3) are not in any FRMR 0.9.43-beta KSI's `controls` array. They produce evidence but contribute nothing to the KSI roll-up. The current README counts them toward "30 detectors" without disclaimer.

**Target:** every detector in the marketed catalog either contributes to a KSI claim OR is honestly named as supplementary 800-53 evidence, not part of the KSI count.

**Acceptance criteria:**
- **For each of the 8 detectors:** investigate whether SC-28 (or SC-12, AC-3) genuinely should map to a FRMR KSI. The strongest candidates: KSI-SVC-RUD ("Removing Unwanted Data") and KSI-SVC-PRR ("Preventing Residual Risk") for encryption-at-rest. If a clean FRMR mapping exists, populate `ksis_evidenced` accordingly and raise a FRMR upstream issue if the FRMR ruleset is missing the link.
- **For unrehomable detectors:** rename the README's headline metric. Instead of "30 detectors", document "N detectors mapped to KSIs + M detectors providing supplementary 800-53 evidence." Both numbers visible. The disclaimer goes in the README's coverage stanza, not buried in DECISIONS.
- **Update `efterlev detectors list` output** to indicate KSI-mapped vs. 800-53-only detectors visually.
- **Track upstream:** if any detector remains 800-53-only because FRMR genuinely lacks the KSI mapping, file an upstream issue at the FRMR repo with the gap and Efterlev's proposed mapping.

**Effort estimate:** 1 week. Mostly investigation + writing; one ruleset PR upstream.

**Deliberately excluded:** inventing fake KSI mappings to inflate the count. That is precisely the marketing-over-substance posture this document is rejecting.

---

## Priority sequencing — recommended order

The priorities are not strictly sequential, but some unblock others:

1. **Priority 0 (module-expansion handling)** lands first — it's the foundation that priorities 1, 2, 3 stand on. Without it, every detector built under priority 1 fires zero against the dominant ICP-A codebase shape, and priority 2's HTML output renders the same thin-evidence story more beautifully.
2. **Priority 6 (honesty pass on `ksis=[]`)** lands second. Cheap, clarifies what we have, sets the honest baseline before priority 1 expands the catalog.
3. **Priority 4 (boundary scoping)** lands next. Touches the data model that priorities 1, 2, 3 will all build on. Doing it early avoids retrofitting.
4. **Priority 1 (detector breadth)** runs in parallel with priorities 2 and 3 — different surfaces, different contributors potentially. Detector work is the longest sustained effort.
5. **Priority 2 (HTML overhaul)** can ship before all of priority 1 lands; it improves whatever evidence is present.
6. **Priority 3 (UX/install)** can ship at any point; small enough to slot opportunistically.
7. **Priority 5 (real customer dogfood + 3PAO)** runs continuously from now; outreach can start immediately, but the meaningful conversation requires priorities 0–4 to be visibly real.

---

## What is deliberately deferred (NOT v1)

The following came up during the v1 planning conversation and are explicitly held until v2+:

- **Live cloud-state correlation.** Reading deployed AWS state and reconciling against IaC. Requires cross-cloud SDKs, IAM, multi-account auth. Months of work. Customers haven't asked.
- **Continuous monitoring daemon.** Drift detection, alerting on regression. Worth building after the point-in-time use case is validated by real customers.
- **Cross-cloud (GCP/Azure).** SaaS-on-AWS is the dominant FedRAMP pattern. Cross-cloud is a v2 expansion, not a v1 requirement.
- **Auto-PR creation from Remediation Agent.** Adds a new trust boundary (writing to remote repos). YAGNI for v1; the local diff path is sufficient.
- **OSCAL output.** Remains v1.5+ per DECISIONS 2026-04-22, gated on first OSCAL-Hub-consuming customer.
- **CR26 migration.** Mid-2026 by FedRAMP; will land as a SPEC when CR26 publishes.
- **Cross-IaC support (Pulumi, CloudFormation, AWS CDK, Helm/k8s manifests).** Each new IaC source is a multi-week parser project. v2 expansion.
- **Authorization-boundary scoping at the AWS-account level.** Repo-relative boundary in v1 is sufficient; account-level boundary requires live state.

---

## Validation gate (the launch tag is downstream of this)

Before tagging v0.1.0, every priority above must clear acceptance. Then:

1. **Re-run the security review** at the new SHA, refreshing every §0 row. The review's structure stays; the numbers change.
2. **Update `docs/launch/runbook.md`** to reflect any priority-1 or priority-3 changes that affect the launch-day actions.
3. **Refresh `LIMITATIONS.md`** — every line that says "we don't do X yet" gets updated to current state.
4. **Refresh `README.md`** headlines: detector count, KSI coverage, theme coverage, "what we cover" stanza.
5. **Maintainer self-review** at the new SHA — sign-off in `docs/security-review-2026-04.md` §8 with the actual reviewed SHA.
6. **Maintainer fresh-eyes runbook walkthrough** per the existing runbook.
7. **Tag `v0.1.0`** and execute hour-0 launch sequence per runbook.

There is no calendar deadline on this gate. There is a quality bar.

---

## Where this work is tracked

- This document is the durable plan; updated as priorities clear acceptance.
- Per-priority work tracked in conventional PRs against `main`, with each PR's body referencing the priority number.
- `docs/launch/post-launch-followups.md` continues to track items NOT in this plan (still genuine v0.1.x / v0.2.0 followups, for items that would have made v0.1.0 if launch had happened today).
- `DECISIONS.md` 2026-04-27 entry captures the strategic-reset decision.
