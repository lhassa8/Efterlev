# How Efterlev fits alongside AWS-native services

If you're pursuing FedRAMP 20x Moderate on AWS, you'll see two patterns
recommended by different sources:

- **AWS-native:** wire AWS Config, Security Hub, CloudTrail, Inspector,
  EventBridge, Step Functions, KMS, IAM Identity Center, Access Analyzer
  (and Landing Zone Accelerator) to produce runtime evidence for the
  Key Security Indicators. AWS published this pattern in two blog posts
  in 2026 — the [primer (2026-02-18)](https://aws.amazon.com/blogs/publicsector/prepare-for-fedramp-20x-with-aws-automation-and-validation/)
  and the [KSI deep-dive (2026-04-27)](https://aws.amazon.com/blogs/publicsector/deep-dive-into-fedramp-20x-key-security-indicators-decoding-the-63-ksis/).
- **Efterlev:** read your Terraform (and `.github/workflows/`) before
  `terraform apply` and produce KSI-classified evidence + a 3PAO-ready
  attestation summary, locally, with no SaaS.

These are **complementary, not competing**. This document explains why,
and how a customer should think about using them together.

---

## The short version

| Question | Answer |
|---|---|
| Do I need both? | Eventually, yes — for FedRAMP 20x on AWS. On Day 1, no: start with Efterlev. |
| Which one first? | **Efterlev first** — it's free, the deterministic scan runs in seconds against a small Terraform tree, and the LLM-backed Gap + Documentation stages typically take a few minutes more. You see where you stand before you provision anything. |
| Which produces the per-KSI attestation summary a 3PAO ingests? | **Efterlev** — its `documentation-{ts}.json` is designed to satisfy the FRMR catalog's CSX-SUM information requirements (goals, consolidated information resources, machine vs non-machine processes, status, clarifications). AWS-native services don't produce a CSX-SUM-shaped artifact today. Empirical 3PAO acceptance is a post-launch validation milestone (real-customer dogfood + 3PAO touchpoint). |
| Which produces the runtime evidence backing those attestations? | **AWS-native** — Config rules, Security Hub findings, CloudTrail logs are the runtime telemetry. |
| What if I'm not on AWS? | Of Efterlev's 38 KSI-mapped detectors, 34 read AWS-resource-shaped Terraform (`aws_*` resources); 4 read `.github/workflows/`. An Azure-only or GCP-only customer running `efterlev scan` against their Terraform gets near-zero KSI evidence today; the GitHub-workflows detectors still fire. Multi-cloud detector coverage (CDK, Pulumi, k8s, Azure ARM, GCP DM) is on the v1.5+ roadmap. |

---

## Three frames for thinking about the fit

### 1. Efterlev is the package generator; AWS-native is the telemetry backing

The artifact a 3PAO ingests for FedRAMP 20x is a structured per-KSI
attestation summary. The FRMR catalog calls this shape `KSI-CSX-SUM`
(see [`csx-mapping.md`](csx-mapping.md)) and lists the required
information per KSI: goals + pass/fail criteria, consolidated
information resources, machine-based vs non-machine validation
processes + persistent cycle, current implementation status,
clarifications.

**No AWS-native service produces a CSX-SUM-shaped artifact today.**
Audit Manager is the closest in spirit and is notably absent from
both AWS posts; if AWS extends Audit Manager toward CSX-SUM-shaped
output, the package-generator overlap with Efterlev grows. Config
rules produce evaluation results; Security Hub aggregates findings;
CloudTrail produces audit logs. Each is *evidence* that backs an
attestation, not the attestation itself.

Efterlev's Documentation Agent produces `documentation-{ts}.json`
**designed to satisfy the CSX-SUM information requirements** — KSI
ID + goals (from the FRMR statement), `cited_evidence_refs[]` mapping
to `source_file:line_range`, narrative explaining what the scanner
saw and didn't see, and an implementation-status field. The Gap
Agent classifies each KSI as implemented/partial/not_implemented;
the Documentation Agent drafts the narrative + cites the evidence.
Both pre-deploy IaC findings (from detectors) and human-signed
Evidence Manifests flow through the same attestation pipeline.

The artifact does **not** today carry the persistent-validation
cadence inline; cadence is supplied by the customer's CI integration
(`pr-compliance-scan.yml` runs on every PR; `report run --watch` runs
on every save). The artifact carries the snapshot.

Empirical 3PAO acceptance is the next validation milestone — a real-customer
dogfood + 3PAO touchpoint, post-launch. Until that closes, the precise
wording is "shaped to satisfy CSX-SUM," not "is the artifact 3PAOs consume."

A 3PAO conversation in this frame, once that validation closes, would
read like:

> *"Here is my Efterlev-generated per-KSI summary (`documentation-*.json`).
> For each KSI, the machine-based validation is backed by both Efterlev's
> pre-deploy detector evidence (cited by source-file:line) and AWS
> Config rule evaluation results (cited by Config-rule-id and timestamp).
> The two sources agree, which is itself an integrity signal. The
> 3-day cadence is enforced by my CI workflow `pr-compliance-scan.yml`,
> visible in the receipt log."*

### 2. Day 1 vs steady-state — a journey overlay

For a small-to-mid SaaS that just got told they need FedRAMP, the
adoption sequence looks like this:

| Phase | What you do | What's involved |
|---|---|---|
| **Day 1** (the moment your CEO says "we need FedRAMP") | `efterlev report run` against your existing Terraform | The deterministic scan completes in seconds for a small Terraform tree. The LLM-backed Gap stage runs in roughly a minute on Opus 4.7. The Documentation Agent's per-KSI narrative pass runs ~30-60s/KSI on Sonnet 4.6, so a full 60-KSI baseline takes **roughly 30 minutes to an hour** end-to-end on first run. No spend, no procurement, posture report in hand. |
| **Week 1-4** | Iterate on `efterlev report run --watch` while the team patches gaps | dev-loop feedback at file-save cadence; AWS-native services not yet stood up |
| **Month 1-3** | Stand up AWS Config + Security Hub + LZA at GovCloud-scale | typically with a consultant; this is the runtime evidence layer |
| **Authorization year** | Both sources feed the 3PAO package | Efterlev produces the per-KSI attestation summary; AWS-native produces the runtime evidence backing it |
| **Steady state** | Config + Security Hub on 3-day cadence; Efterlev on every PR + every save | dev-loop + runtime-loop both alive |

The AWS-native stack is heavy enough that "do it before authorization"
isn't realistic for most ICP-A customers. Efterlev fits the
pre-authorization shape; AWS-native fits the steady state. They
overlap in steady-state, where they double-evidence the same KSI from
two angles.

### 3. The dev-loop is something AWS-native structurally cannot replicate

`efterlev report run --watch` re-runs the full pipeline on every file
save (debounced 2s). When you edit a `.tf` file, you see updated
KSI evidence in seconds.

AWS Config rules evaluate **deployed** resources. There is no
file-save trigger; the resource has to exist for Config to see it.
The 3-day cadence FedRAMP 20x asks for in Phase 2 is a runtime
cadence, not a development cadence.

This is the strongest single positioning anchor: **Efterlev gives you
KSI feedback in the loop where it's cheapest to fix things — before
the resource exists.**

---

## Where the coverage actually lands

Both tools cover meaningful but non-identical KSI surfaces. From AWS's
[2026-04-27 deep-dive blog](https://aws.amazon.com/blogs/publicsector/deep-dive-into-fedramp-20x-key-security-indicators-decoding-the-63-ksis/),
AWS-native services are explicitly mapped to roughly 14 thematic KSIs
(plus partial coverage across many more):

- **CNA** (Cloud Native Architecture): KSI-CNA-MAT, RNT, EIS via VPC,
  Network Firewall, Config drift detection.
- **IAM**: KSI-IAM-MFA via Identity Center; KSI-IAM-ELP via Access
  Analyzer; KSI-IAM-JIT referenced.
- **SVC** (Service Configuration): KSI-SVC-SNT, VRI via KMS + ACM;
  KSI-SVC-ACM via CloudFormation.
- **MLA** (Monitoring/Logging/Auditing): KSI-MLA-OSM via Security Hub
  + CloudWatch; KSI-MLA-EVC via Config conformance packs.
- **AFR** (Authorization by FedRAMP): KSI-AFR-VDR via Inspector +
  Security Hub; KSI-AFR-SCN via CloudTrail + EventBridge.

Efterlev today covers **31 of 60 thematic KSIs** at the IaC layer.
The overlap with AWS-native's named KSIs is ~10-12 KSIs (mostly in
CNA, IAM, MLA, SVC) — the same KSI gets evidenced from both angles:
Efterlev catches the IaC misconfig; AWS-native confirms the runtime
behavior.

The non-overlapping pieces:

- **Efterlev-only at the IaC layer:** KSI-CMT-VTD/RMV/LMC (CI-pipeline
  validation, immutable deploy patterns, change logging), KSI-SCR-MIT
  (action pinning), KSI-IAM-AAM (IAM-managed-via-Terraform),
  KSI-PIY-GIV (Terraform inventory), KSI-RPL-TRC (backup restore
  testing), KSI-SVC-RUD (S3 lifecycle), KSI-SVC-VCM (CloudFront HTTPS).
- **AWS-native-only at runtime:** real-time GuardDuty findings,
  CloudTrail event-based alerting, Inspector-discovered runtime CVEs,
  Config drift over time.

A FedRAMP 20x Phase 2 customer needs automated validation for at
least **70% of the KSIs** in their authorization package. The
threshold applies to the customer's *whole* package — not to any
single tool. Honest accounting on these two tools alone:

- Efterlev covers **31 of 60** thematic KSIs at the IaC layer.
- AWS-native services cover **~14** thematic KSIs explicitly, with
  partial coverage across more.
- The intersection is ~10–12 KSIs (CNA, IAM, MLA, SVC).
- Union ≈ 30 + 14 − 11 = **~33 of 63 KSIs** (~52%) — distinct layers,
  not double-counted.

That's *below* the 70% threshold. Important nuance about the
threshold itself: FedRAMP 20x Phase 2's 70% language asks specifically
for *automated* validation. Procedural Evidence Manifests are
human-signed attestations, not automated validation — they cover the
AFR / CED / INR themes and the 3 procedural CSX KSIs (which the
scanner can't see at all), but they don't count toward the 70%
*automated*-validation bar. Reaching 70% automated coverage on a
procedural-heavy posture means standing up runtime telemetry
(GuardDuty findings on a 3-day cadence, Inspector continuous scans,
Config conformance pack evaluations, Security Hub findings) on top of
Efterlev's pre-deploy IaC layer + AWS-native services' runtime
evaluation layer. Manifests close the *KSI* coverage gap; runtime
telemetry closes the *automated-validation* gap.

The phrase "Efterlev + AWS-native is all you need" is not accurate;
"Efterlev pre-deploy + AWS-native runtime + a procedural manifest
layer + a runtime-telemetry pipeline" is the honest picture.

---

## Where Efterlev is *not* a fit (be honest)

- **You're 100% AWS, technically deep, and want to build your own
  evidence pipeline using LZA + EventBridge + Step Functions
  yourself.** Efterlev provides less marginal value for you; the
  win is "we save you the dev-loop build effort." Many sophisticated
  AWS shops still prefer Efterlev for the package-generator + dev-loop
  shape, but it's not a forced choice.
- **You're going to use AWS Audit Manager as your primary attestation
  surface.** Audit Manager doesn't produce CSX-SUM-shaped output today,
  but it's the AWS-native service most likely to evolve into one. If
  AWS extends Audit Manager toward CSX-SUM (or publishes its own
  shape that becomes the FedRAMP-acceptable artifact), Efterlev's
  package-generator advantage narrows materially. Today the conflict
  is theoretical, not active — but worth tracking as a live risk to
  this positioning rather than dismissing.
- **You're not pursuing FedRAMP 20x.** Efterlev's value is KSI-native
  classification. If you're on FedRAMP Rev5 or another standard,
  Efterlev's KSI shape may not map cleanly.

---

## What to put in front of a buyer

A buyer arriving from the AWS blog post should see, in this order:

1. "Efterlev runs **before** your AWS-native services have anything
   to evaluate. It reads your Terraform and tells you where you stand
   today, with no spend."
2. "Efterlev produces a per-KSI summary **shaped to satisfy the FRMR
   catalog's CSX-SUM information requirements** — goals, consolidated
   information resources, machine vs non-machine processes, status,
   clarifications. AWS-native services produce the runtime telemetry
   that backs that summary. (Empirical 3PAO acceptance is being
   validated in v0.1.x.)"
3. "If you're already running AWS Config and Security Hub, Efterlev
   gives you the dev-loop layer they structurally cannot — feedback
   on every file-save."
4. "Together, Efterlev (pre-deploy IaC) and AWS-native (runtime
   telemetry) cover distinct layers of the 63-KSI surface; a serious
   FedRAMP 20x customer typically wires both, plus a runtime-telemetry
   pipeline on a 3-day cadence."

These are four sentences. Use them.
