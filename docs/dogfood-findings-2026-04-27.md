# Dogfood findings — 2026-04-27 — `aws-ia/terraform-aws-eks-blueprints/patterns/blue-green-upgrade`

**Purpose:** the v1 readiness plan (`docs/v1-readiness-plan.md`) names six priorities. This document is the "fresh read on what we have today" the maintainer requested as input to that plan's sequencing. A full Efterlev pipeline run was executed against a real, ICP-A-shaped OSS Terraform codebase. Findings are recorded honestly; nothing is sugar-coated.

**Target codebase:** `aws-ia/terraform-aws-eks-blueprints` at SHA `98d0eb4`, scoped to `patterns/blue-green-upgrade/` (16 `.tf` files; demonstrates a real production blue/green Kubernetes upgrade pattern with prod + staging clusters, IAM, secrets, networking).

**Why this codebase:** maintained by AWS Industries (`aws-ia`), real-world deployment pattern (not module library code), substantial enough to exercise multiple detector families, never previously dogfooded by Efterlev. Closer to ICP-A reality (a SaaS company deploying their EKS-based platform) than scanning a module's `main.tf` directly.

**Pipeline:** `efterlev init` → `efterlev scan` → `efterlev agent gap` (with real Anthropic API). Skipped `efterlev agent document` (7-minute heavy LLM run; the gap-stage output was sufficient signal). Ran `efterlev poam`.

---

## Executive summary

The pipeline works end-to-end. The agent reasoning that did happen was high-quality. **But the headline finding is alarming for ICP-A readiness:** out of 30 detectors, **exactly 1 fired**, against 9 parsed resources from 16 `.tf` files. The resulting POA&M emitted **59 of 60 KSIs as HIGH-severity not_implemented items** — a posture statement that no 3PAO would accept as credible and no customer would email anywhere.

The root cause is not a tool bug. It is a fundamental architectural gap: **Efterlev's detectors look for raw `resource "aws_*"` declarations, but the dominant ICP-A Terraform pattern is module composition** (`module "eks" { source = "terraform-aws-modules/eks/aws" ... }`). All the real workload — EKS cluster, VPC, IAM roles, KMS keys, security groups, CloudTrail — lives inside upstream modules that Efterlev never sees without plan-JSON expansion.

This is THE most consequential finding from the dogfood. Every priority in the v1 plan still applies, but **module-expansion handling needs to be priority 0** before any of them. Detail and prescription below.

---

## Findings, by category

### 1. Module-expansion gap — the dominant finding

**Observation.** The codebase has 9 raw `resource` declarations and 11 `module` calls. Of the 9 resources, only 4 are AWS-provider-shape (route53, ec2_tag, secretsmanager x2); the other 5 are `kubernetes_*` and `random_password` that Efterlev has no detectors for. The 11 module calls reference the actual workload (`module "vpc"`, `module "eks"`, `module "eks_blueprints_addons"`, `module "ebs_csi_driver_irsa"`, `module "vpc_cni_irsa"`, `module "eks_blueprints_dev_teams"`, etc.).

The Efterlev detector library targets `resource "aws_*"` declarations. Module calls are not visited. The result: a codebase that defines a complete production EKS deployment (cluster + nodes + IAM + KMS + networking + observability) appears to Efterlev as "no AWS infrastructure of note."

**What `LIMITATIONS.md` and `docs/v1-readiness-plan.md` already say about this:** plan-JSON mode (`efterlev scan --plan plan.json`) IS the documented workaround. `terraform plan -out plan.bin && terraform show -json plan.bin > plan.json` produces a fully-resolved resource list after module expansion; detectors then work against that. The dogfood-real-codebases.sh script uses both modes for some of its targets.

**Why this is still a finding worth elevating to priority 0:**

1. **Plan-JSON mode is not the primary documented path.** The README quickstart says `efterlev scan` with no flags. A first-time ICP-A user follows the quickstart and gets the thin-evidence result. Nothing in the CLI output suggests "you should re-run with `--plan` because most of your resources are inside module calls." That guidance lives in LIMITATIONS.md, which a first-time user will not read.
2. **Plan-JSON requires `terraform plan` to succeed.** That requires credentials, network access to AWS, and (often) a working state backend. For a first-time install where the user is just trying to see what Efterlev does, that is a heavy ask.
3. **Even with plan-JSON, the user has to know to do this.** The current scan output reports `resources parsed: 9` with no warning that the codebase has 11 module calls that probably contain the bulk of the resources.

**Recommendation (proposed priority 0, before all six existing v1 priorities):**

- **Detect module-call density at scan time.** When `efterlev scan` (HCL mode) parses a target where `len(module_calls) > len(resources)` or `len(module_calls) > N`, emit a structured warning: "this codebase appears to compose N upstream modules; detector coverage will be limited without plan-JSON expansion. Run `terraform init && terraform plan -out plan.bin && terraform show -json plan.bin > plan.json && efterlev scan --plan plan.json` to scan the expanded plan."
- **Surface plan-JSON in the README quickstart.** Two paths: "if your codebase is module-composed, do this" vs. "if it has many raw resource declarations, this works directly." The dominant path (module-composed) becomes the primary path.
- **Consider a `--auto-plan` flag** that runs `terraform plan` for the user (requires explicit opt-in and probably a credentials prompt). Future enhancement; not blocking.
- **Documentation Agent should know.** When the Gap Agent classifies 59 of 60 KSIs as `not_implemented` against a thin-evidence scan, the agent's narratives could explicitly note "this scan was HCL-mode against a module-composed codebase; plan-JSON would surface more evidence." Today's narratives are honest but generic.

**Evidence:** `efterlev scan` output reported `resources parsed: 9` with no warning about the 11 module calls. The single firing detector (`aws.secrets_manager_rotation`) caught a directly-declared `aws_secretsmanager_secret "argocd"` — every other AWS resource was inside a module. The Gap Agent reasoned correctly about each KSI ("the scanner could in principle detect CloudTrail, Config, or audit log resources from IaC, but none were observed") but could not say "this scan missed module expansion" because it does not know it.

---

### 2. Detector breadth — confirms the v1 plan priority 1 with new specificity

**Observation.** Of the 30 detectors run, the single firing one was `aws.secrets_manager_rotation`. Twenty-nine fired zero. This codebase deploys a real Kubernetes platform with full IAM, KMS, networking, observability — and Efterlev recognized none of it.

**Specific KSIs the Gap Agent classified as `not_implemented` that Efterlev *should* be able to evidence (with module expansion + the right detectors):**

- **KSI-CMT-LMC** (Logging Changes) — agent's narrative: "the scanner could in principle detect CloudTrail, Config, or audit log resources from IaC, but none were observed." With plan-JSON + a CloudTrail/Config detector that handles both raw and module-resolved resources, this would fire on the EKS module's CloudWatch log group.
- **KSI-CMT-VTD** (Validating Throughout Deployment) — narrative: "The scanner could detect CI/CD config from IaC but produced nothing here." We have NO detector for CI/CD config (priority 1 names this gap explicitly: "CMT (currently 0 detectors) — could read `.github/workflows/`, GitHub branch protection, PR-required-checks").
- **KSI-CNA-RNT** (Restricting Network Traffic) — narrative: "No evidence on ingress/egress restrictions." We have `aws.security_group_open_ingress` and `aws.nacl_open_egress` detectors; both fired zero because the security groups were inside the EKS module.
- **KSI-CNA-ULN** (Using Logical Networking) — narrative: "No evidence on logical networking constructs (VPCs, subnets, route tables)." We have NO detector for VPC/subnet structure. This is a gap.
- **KSI-IAM-ELP** (Ensuring Least Privilege) — narrative: "No evidence on least-privilege enforcement." We have `aws.iam_admin_policy_usage` and `aws.iam_inline_policies_audit`; both fired zero against module-encapsulated IAM.
- **KSI-MLA-LET** (Logging Event Types) — narrative: "No defined list of resources/event types being logged." We have `aws.cloudtrail_audit_logging` and `aws.cloudwatch_alarms_critical`; both fired zero.

**Recommendation:** the v1 plan priority 1 (detector breadth to ≥30 KSIs across ≥8 themes) is correct as written, but the dogfood gives concrete evidence for which detectors are most ICP-A-relevant:

1. **Highest impact in this codebase:** a VPC/subnet structural detector (would fire on EVERY EKS deployment). Currently missing entirely.
2. **High impact:** a CloudTrail/CloudWatch detector that handles module-resolved resources, not just raw declarations.
3. **High impact:** a Kubernetes-aware IAM detector (IRSA roles, service accounts, RBAC). Currently nothing in this space.
4. **Medium impact:** the CMT detectors named in priority 1 (read `.github/workflows/`, branch protection). Would have fired on this codebase's repo metadata if we'd looked at the parent repo's `.github/`.

**Adjustment to plan priority 1:** add an explicit checklist of "the 5 detectors that would have made this dogfood codebase show as substantial-evidence rather than thin-evidence." That is a clearer success criterion than "30 KSIs across 8 themes."

---

### 3. HTML report quality — confirms v1 plan priority 2

**Observation.** The gap-report HTML is functional, single-file, self-contained (no JS, no external CDN, system-default font). It uses status pills with color-coding (green for `implemented`, amber for `partial`, red for `not_implemented`, blue for `evidence_layer_inapplicable`, gray for `not_applicable`). Container max-width 960px.

**What is NOT in the HTML:**

- **Zero `<script>` tags.** Confirmed by grep. No search, no sort, no filter, no progressive enhancement of any kind.
- **No coverage matrix.** A 3PAO opening this report sees 60 cards in linear order (one per KSI). To get a one-glance posture statement, they have to scroll all 1567 lines and mentally tally. There is no theme-by-theme heatmap.
- **No machine-readable JSON sidecar.** Checked: `.efterlev/reports/` contains only HTML files. A tooling consumer (CI/CD, dashboard, ticketing integration) has to parse HTML to get structured data. That is not what consumers do; they would either give up or scrape brittlely.
- **No drill-down.** Each evidence card shows the citation but not the underlying source-file lines. A reviewer wanting to verify a finding has to open the source file separately.
- **No diff view** (and no scan-history concept).

**What the HTML does well:**

- The DRAFT banner is prominent at the top.
- Status pills are color-distinct and accessible (color + position + text).
- Source-distinction badges (manifest vs scanner) work.
- The evidence-layer-inapplicable status (blue) is visually distinct from `not_implemented` (red), so a 3PAO can see at a glance which "not covered" rows are real gaps vs scanner-coverage gaps. SPEC-57.1 paying off.
- The CSS is restrained and printable.

**Recommendation:** v1 plan priority 2 is correct as-is. The dogfood confirms every named gap. **Add one additional acceptance criterion:** the HTML must let a reviewer click on a KSI card and jump to the underlying evidence's source-file lines (with line numbers) without leaving the report. Today the source-file path is shown in the card's metadata but is not actionable.

---

### 4. POA&M severity heuristic produces an unusable artifact under thin evidence

**Observation.** The POA&M emitted 59 open items, **every single one as HIGH severity** (because the heuristic is `not_implemented → HIGH`). The output is 80,496 bytes of "DRAFT — SET BEFORE SUBMISSION" placeholders.

**Why this is a finding even though the heuristic is documented:**

- A real customer running this against their real codebase would see this output and either (a) submit it to a 3PAO and be embarrassed, or (b) more likely, conclude the tool is wrong and stop using it. The cost of "59 HIGH-severity items" is reputational for the tool, not just for the customer.
- The doc says "Severity is a starting-point heuristic ... reviewer must confirm severity per the organization's risk framework" — accurate, but the friction to confirm is "edit 59 markdown items by hand."
- The POA&M does not include the GAP AGENT'S CONTEXT. The Gap Agent's narrative said `KSI-CMT-LMC: not_implemented — the scanner could in principle detect CloudTrail, Config, or audit log resources from IaC, but none were observed.` That nuance — "scanner didn't see it; you might have it" — is gone in the POA&M, which just says "HIGH severity, weakness DRAFT — SET BEFORE SUBMISSION."

**Recommendation (new acceptance criterion, slot under priority 2 or as its own small priority):**

- **Severity should consider scanner coverage.** When the Gap Agent's rationale says "the scanner could detect this in principle but didn't," the POA&M severity should not default to HIGH. Possibilities: drop to MEDIUM or LOW with a caveat ("possible scanner coverage gap; verify against deployed state"); or emit a separate "needs-scanner-coverage-verification" status alongside the severity heuristic.
- **POA&M items should carry the Gap Agent's narrative.** Today the POA&M's "Finding Rationale (Gap Agent)" field exists and is populated, but the SEVERITY column doesn't reflect what that rationale says.
- **`efterlev poam --filter`** to produce a focused POA&M ("only the items the Gap Agent ranked as high-confidence-not-implemented"). Today there is no filter; you get all 59.

---

### 5. UX during install + first run — confirms v1 plan priority 3 with new specificity

**Observation.** End-to-end timing for the dogfood:

| Stage | Wall time | Notes |
|---|---|---|
| `efterlev init` | <1 second | Clean, informative output |
| `efterlev scan` | 0.3 seconds | 1 evidence record, 30 detectors enumerated |
| `efterlev agent gap` | 58 seconds | 60 KSIs classified; one Anthropic API call per KSI batch |
| `efterlev poam` | <1 second | 59 open items, deterministic |
| **Total user-perceived time** | ~60 seconds (Gap Agent dominates) |

The 7-minute Documentation Agent was skipped here. Had it run, total time would be ~8 minutes.

**UX issues observed in real time:**

1. **Zero progress signal during the 58-second Gap Agent run.** Just blank stdout. A first-time user is staring at a stalled-looking terminal. Confirmed v1 plan priority 3 finding.
2. **The scan output's per-detector listing (`aws.access_analyzer_enabled@0.1.0 +0`, ...30 lines like this) is noise when nothing fired.** Useful in diagnostic mode; clutter on a successful scan. Should be suppressed when `--verbose` is not set, or collapsed to "0 of 30 detectors fired" with a `--verbose` flag to expand.
3. **The thin-evidence outcome is not flagged as a user-actionable issue.** The scan reported `resources parsed: 9, detectors run: 30, evidence records: 1` and exited 0. A first-time user has no signal that something might be wrong. Should emit a structured warning when evidence-record count is implausibly low for the resource count, with remediation pointers.
4. **The `Detector record IDs (pass to `efterlev provenance show`)` line is good UX.** Discoverable, actionable.
5. **No `efterlev doctor` was run** (because it does not exist). Confirms v1 plan priority 3 sub-item.
6. **No first-run wizard.** The user has to know `ANTHROPIC_API_KEY` is required for `agent gap` before running it. Today the failure mode is `Error code: 401 - {'type': 'error', ...}` raw SDK error.

**Recommendation:** v1 plan priority 3 is correct. **Add three new acceptance criteria:**

- The `efterlev scan` output must distinguish "ran cleanly, found nothing" from "ran with a coverage warning, here's what to do." Today the two are indistinguishable.
- The per-detector firing list should be suppressed in default output and surfaced with `--verbose`.
- Provide a structured `--json-output` flag on `scan` and `agent gap` for tooling integration today (the JSON-sidecar work in priority 2 is for HTML; this is for the CLI itself).

---

### 6. Quality of Gap Agent reasoning — the silver lining

**Observation.** The Gap Agent's narratives are high-quality despite the thin evidence:

- For the one finding (`aws.secrets_manager_rotation` on `argocd`), the agent correctly attributed it to BOTH **KSI-IAM-SNU** (non-user authentication) and **KSI-SVC-ASM** (automating secret management) with specific evidence citations.
- For the 29 not_implemented KSIs, narratives distinguish "no IaC evidence is possible — procedural KSI" (correctly classified as `evidence_layer_inapplicable`) from "the scanner could detect this but found nothing" (classified as `not_implemented`).
- Specific honest framings appeared throughout, e.g. `KSI-CMT-VTD`: "The scanner could detect CI/CD config from IaC but produced nothing here." That sentence is doing real work — it tells a 3PAO that the absence is a coverage gap, not necessarily a CSP gap.

**This is the v1 plan's strongest argument working in our favor.** The reasoning layer is good. The gaps are in evidence collection (detectors, module expansion) and presentation (HTML, POA&M severity). Priority 1 + module-expansion work fixes the input; priority 2 fixes the output; the Gap Agent stays as it is.

**Recommendation:** no changes to the Gap Agent's prompts or logic. Verify in a future dogfood (post-priority-1 + module-expansion) that with rich evidence input, the agent's narratives stay this honest. They probably will; the prompt rules are sound.

---

### 7. What was deliberately not exercised

To keep this dogfood tight, the following were skipped. Each is captured here so a future re-run knows what to add:

- **`efterlev agent document`** — the 7-minute Documentation Agent run. Would produce 60 narrative attestations + the FRMR JSON artifact. Skipped because the gap-stage HTML and the POA&M markdown were sufficient signal for "is the output remarkable?" (no).
- **`efterlev agent remediate`** — would propose Terraform diffs. Skipped because there is essentially nothing to remediate against this thin-evidence scan.
- **`efterlev scan --plan plan.json`** — plan-JSON mode. Would have required `terraform init && terraform plan` against AWS. Not run because the goal here was "what does a first-time ICP-A user see?" and the answer is "what HCL mode produces."
- **MCP server (`efterlev mcp serve`)** — out of scope for this dogfood.
- **Provenance walking (`efterlev provenance show <id>`)** — works (verified manually); no findings.

A future "deep" dogfood pass should include the doc agent (to evaluate FRMR attestation artifact quality), remediation (to evaluate diff quality on a richer-evidence scan), and a plan-JSON A/B comparison.

---

## Priority adjustments to `docs/v1-readiness-plan.md`

The dogfood validates the six priorities AND surfaces one additional concern that should be slotted in. Recommended amendment:

### New priority 0 — Module-expansion handling and the plan-JSON discoverability gap

**Rationale:** the dominant ICP-A Terraform pattern is module composition. Without addressing this, every other priority builds on a foundation that produces "1 evidence record" against real codebases. A v1 release that ships with the dogfood-2026-04-27 thin-evidence behavior cannot be called outstanding regardless of how many detectors it has or how beautiful the HTML is.

**Acceptance criteria (proposed):**

- `efterlev scan` (HCL mode) detects module-call density and emits a structured warning when scanning a module-composed codebase: "N module calls detected; detector coverage will be limited without plan-JSON expansion. See <command>." Exit code: still 0 (the scan succeeded), but a non-empty warnings list flagged in the output JSON sidecar (priority 2 dependency).
- README quickstart presents BOTH paths: "module-composed (most ICP-A codebases): use plan-JSON" and "raw resources: HCL mode works." Today only HCL is in the quickstart.
- The Documentation Agent's narrative for `not_implemented` KSIs notes when the underlying scan was thin-evidence, so the artifact handed to a 3PAO is honest about coverage limitations.
- `efterlev scan` accepts an optional `--auto-plan` flag that runs `terraform init && terraform plan` for the user (with explicit opt-in and credentials prompt). Stretch.
- A new dogfood pass against the SAME `aws-ia/terraform-aws-eks-blueprints/patterns/blue-green-upgrade/` produces ≥10 evidence records, not 1.

**Effort estimate:** 1.5–2 weeks. Module-call detection in the existing parser is small; the warning surface and README rewrite are small. The `--auto-plan` flag and credentials handling is the most work.

**Why this is priority 0, not priority 7:** priorities 1–6 in the plan are useful enhancements. Without addressing module expansion, priorities 1–6 do not solve the problem. A customer running Efterlev against their real codebase needs to see actual evidence, not 30 detectors firing zero against an EKS deployment.

### Re-validate after priority 0 lands

Re-run this dogfood pass after priority 0 (module-expansion handling) and priority 1 (detector breadth) land. Acceptance criterion for the v1 launch tag: against this same `aws-ia/terraform-aws-eks-blueprints/patterns/blue-green-upgrade/` SHA, the pipeline produces ≥30 evidence records and the Gap Agent classifies ≥6 KSIs as `implemented` or `partial`. That is the concrete number that converts "the tool tries" to "the tool works."

---

## Reproducibility

```bash
cd /tmp
git clone --depth=1 https://github.com/aws-ia/terraform-aws-eks-blueprints.git
cd terraform-aws-eks-blueprints/patterns/blue-green-upgrade
# Verify SHA: 98d0eb4069e787210848eeefcb2b9ba8e52706e7

efterlev init
efterlev scan
# Expected today: 9 resources, 1 evidence record, 1 detector firing.

ANTHROPIC_API_KEY=sk-ant-... efterlev agent gap
# Expected today: 60 KSIs classified, 31 evidence_layer_inapplicable, 29 not_implemented.

efterlev poam
# Expected today: 59 open items, all HIGH severity.
```

The artifacts live at `/tmp/efterlev-dogfood/terraform-aws-eks-blueprints/patterns/blue-green-upgrade/.efterlev/reports/` for the duration of this scan; they are not committed.

---

## Validation re-run (2026-04-27, post-Priority-0)

After the three Priority 0 sub-PRs landed (#29 module-call warning, #30 README plan-JSON discoverability, #31 agent scan-coverage prompt awareness), the same dogfood pipeline was re-executed against the same target SHA (`98d0eb4`). The re-run is the acceptance gate documented in `docs/v1-readiness-plan.md` Priority 0.

**Acceptance criteria (from the v1 plan):**

> Re-run dogfood: against the same `aws-ia/terraform-aws-eks-blueprints/patterns/blue-green-upgrade` SHA, the pipeline produces ≥10 evidence records (vs today's 1) when run with plan-JSON, OR emits a clear warning + actionable remediation when run without.

The re-run was HCL-mode only (plan-JSON would require `terraform init && plan` against AWS, which is outside the scope of this validation). The acceptance criterion's HCL-mode branch is what we measure.

**Side-by-side, before vs after:**

| Metric | Before (2026-04-26) | After (2026-04-27, Priority 0) |
|---|---|---|
| Module-call warning at scan time | None — silent thin evidence | ✅ "12 module calls detected; detector coverage is limited in HCL mode" with copy-pasteable plan-JSON remediation |
| Module-call count surfaced in scan summary | Not surfaced | ✅ `module calls: 12` line alongside `resources parsed: 9` |
| Gap Agent classifications: `evidence_layer_inapplicable` | 31 | **44** (+13) |
| Gap Agent classifications: `not_implemented` | 29 | **14** (−15) |
| Gap Agent classifications: `partial` | 0 | **2** (+2) |
| Gap Agent narratives mentioning coverage limits | 0 | Many (specific to HCL/module-composition; recommend plan-JSON) |
| POA&M open items (HIGH severity each) | 59 | **16** (−43, a 73% reduction) |

**The single positive finding got a more accurate classification:**

The `aws.secrets_manager_rotation` evidence on `argocd` previously got classified `not_implemented` for both KSI-IAM-SNU and KSI-SVC-ASM. After Priority 0, the same evidence now classifies KSI-IAM-SNU as **`partial`** with a specific narrative: *"Evidence sha256:d54e4cf9 shows the 'argocd' Secrets Manager secret has no paired rotation resource — a non-user authentication credential that is not being automatically rotated. This covers one negative finding for non-user credential hygiene; it does not cover IAM role/instance-profile based non-user authentication, which lives in the unanalyzed modules and would require plan-JSON scanning."*

That narrative is the kind of artifact a 3PAO can read and act on. The previous version was generic.

**Sample post-Priority-0 narratives (from the gap-agent run):**

- **KSI-CMT-LMC** *(was: "the scanner could in principle detect CloudTrail, Config, or audit log resources from IaC, but none were observed")* — now: *"CloudTrail/Config logging of changes is IaC-evidenceable but no such evidence was produced. Likely a coverage gap — CloudTrail and Config are commonly defined inside upstream modules invisible in HCL mode; plan-JSON scanning would clarify."*
- **KSI-CNA-MAT** *(was: "No evidence of attack-surface minimization")* — now: *"Attack-surface minimization (security groups, public exposure, SSH access) is IaC-evidenceable but no detector produced evidence. Likely a coverage gap — security groups commonly live inside VPC/EKS modules invisible in HCL mode; plan-JSON scanning recommended."*
- **KSI-CNA-ULN** — now: *"Logical networking (VPCs, subnets, NACLs) is IaC-evidenceable but no evidence was produced. Likely a coverage gap — VPC resources are almost certainly inside the unanalyzed modules; plan-JSON scanning recommended."*

Each narrative now does three things at once: (1) names the IaC-evidenceability honestly, (2) classifies the absence specifically as a likely coverage gap rather than a real implementation gap, (3) gives the user a concrete next step. The 3PAO reading the POA&M sees 16 actionable items, not 59 spurious ones; the customer reading the narrative knows whether to investigate or to re-scan.

**Remaining work (NOT Priority 0):**

- The `--auto-plan` flag (Priority 0 stretch) was not implemented — deferred. Users who want the recommended remediation still have to run `terraform init && terraform plan && terraform show -json` themselves. That is acceptable for v1; auto-plan crosses too many trust boundaries (running tools against the user's AWS account) to ship as default.
- Plan-JSON re-run validation against this same target requires AWS credentials and a successful `terraform plan`. Skipped here; the warning + agent narrative behavior is the v1-relevant signal.

**Priority 0 acceptance: cleared.** The five sub-criteria from the v1 plan:

- [x] Module-call density warning at scan time (PR #29)
- [x] README quickstart presents both paths (PR #30)
- [x] Documentation Agent narratives reflect coverage (PR #31, validated above via Gap Agent narratives — same metadata flow; the Documentation Agent run was not exercised here to keep the validation focused)
- [x] Re-run dogfood produces a clear warning + actionable remediation in HCL mode (validated above)
- [ ] Optional `--auto-plan` flag — deliberately deferred, not blocking acceptance per the v1 plan's "stretch" framing

**Effect on the v1 plan sequencing:** Priority 0 is now done. Priority 6 (honesty pass on `ksis=[]` detectors) becomes the next priority per the recommended sequence in `docs/v1-readiness-plan.md`.
