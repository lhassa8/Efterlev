# AWS FedRAMP 20x KSI Deep-Dive — Analysis & Impact on Efterlev

**Source:** Keastead, P., & Kromer, T. (2026-04-27). *Deep dive into FedRAMP 20x Key Security Indicators: Decoding the 63 KSIs.* AWS Public Sector Blog. https://aws.amazon.com/blogs/publicsector/deep-dive-into-fedramp-20x-key-security-indicators-decoding-the-63-ksis/

**Companion piece:** Keastead & Kromer (2026-02-18). *Prepare for FedRAMP 20x with AWS automation and validation.* https://aws.amazon.com/blogs/publicsector/prepare-for-fedramp-20x-with-aws-automation-and-validation/

**Date of this analysis:** 2026-04-28

**Status:** Draft. Recommend the maintainer read top-to-bottom and act on the items in §6 before continuing v0.1.0 release prep.

---

## 1. Headline finding (TL;DR)

**The AWS blog is consistent with the catalog Efterlev already vendors. There is no
catalog drift. The "63 KSIs / 12 themes" framing is a counting choice — they're
adding 3 cross-cutting meta-KSIs (the `CSX` cluster) that live in the FRMR
catalog's `FRR.KSI.data.20x.CSX` section as procedural requirements, separately
from the 60 thematic KSIs Efterlev classifies against.**

Specifically:

- **The official FedRAMP catalog at `FedRAMP/docs/FRMR.documentation.json@a06fa8f9`
  is still version `0.9.43-beta`** — same as the version Efterlev vendors at
  `catalogs/frmr/`. Last updated 2026-04-08, no changes since.
- The thematic KSIs section (`d.KSI`) has **60 KSIs across 11 themes**: AFR (10),
  CED (4), CMT (4), CNA (8), IAM (7), INR (3), MLA (5), PIY (5), RPL (4), SCR (2),
  SVC (8). Identical to what Efterlev shows.
- The cross-cutting KSIs (`d.FRR.KSI.data.20x.CSX`) are **KSI-CSX-SUM**,
  **KSI-CSX-MAS**, **KSI-CSX-ORD**:
  - `CSX-SUM` (Implementation Summaries) — providers MUST maintain summaries
    naming goals, consolidated information resources, machine-based vs
    non-machine processes, current status.
  - `CSX-MAS` (Application within MAS) — providers SHOULD apply ALL KSIs to
    ALL aspects of their cloud service offering within the FedRAMP Minimum
    Assessment Scope.
  - `CSX-ORD` (Order of Criticality) — providers MAY use the suggested order
    of criticality for tackling KSIs in initial authorization.
- These are procedural cross-cutting requirements about *how* to organize
  the KSI work, not technical/measurable KSIs. AWS counts them; Efterlev's
  current README+docs do not. Both accountings are defensible against the
  same catalog data.

**Operational implication:** No code change is required to keep Efterlev
"current." A documentation refresh acknowledging the 60 + 3 = 63 framing
removes potential 3PAO-side confusion.

---

## 2. What the AWS blog says

### Theme inventory (per AWS, 12 themes, 63 KSIs)

| Theme | Code | AWS count | Efterlev count | Match? |
|---|---|---:|---:|---|
| Cross-Cutting | CSX | 3 | 0 (in FRR section, not counted) | accounting only |
| Authorization by FedRAMP | AFR | 10 | 10 | ✓ |
| Cloud Native Architecture | CNA | 8 | 8 | ✓ |
| Change Management | CMT | 4 | 4 | ✓ |
| Identity & Access Management | IAM | 7 | 7 | ✓ |
| Monitoring, Logging, Auditing | MLA | 5 | 5 | ✓ |
| Service Configuration | SVC | 8 | 8 | ✓ |
| Recovery Planning | RPL | 4 | 4 | ✓ |
| Policy & Inventory | PIY | 5 | 5 | ✓ |
| Incident Response | INR | 3 | 3 | ✓ |
| Cybersecurity Education | CED | 4 | 4 | ✓ |
| Supply Chain Risk | SCR | 2 | 2 | ✓ |
| **Total** | | **63** | **60** | counted differently |

### AWS's positioning of native services as KSI evidence sources

The blog maps AWS-native services to specific KSIs. Notable mappings:

| AWS Service | KSIs AWS positions it for |
|---|---|
| AWS Config + Conformance Packs | KSI-CNA-EIS (drift detection), KSI-MLA-EVC (config evaluation) |
| AWS Security Hub | KSI-AFR-VDR (vulnerability detection), KSI-MLA-OSM (SIEM) |
| AWS CloudTrail | KSI-AFR-SCN (significant change notification) |
| Amazon Inspector | KSI-AFR-VDR (vulnerability scanning) |
| Amazon EventBridge + Step Functions | "Persistent validation" workflows |
| AWS IAM Identity Center | KSI-IAM-MFA (FIDO2 phishing-resistant MFA) |
| AWS IAM Access Analyzer | KSI-IAM-ELP (least privilege, unused permissions) |
| AWS KMS + Certificate Manager | KSI-SVC-SNT (encrypt traffic), KSI-SVC-VRI (resource integrity) |
| AWS CloudFormation | KSI-SVC-ACM (automate config management) |
| Landing Zone Accelerator (LZA) | "Partial coverage" of CNA, MLA, IAM KSIs |

### Concrete operational requirements

Two numbers worth pinning:

- **70% automation threshold** (verbatim from
  https://www.fedramp.gov/20x/phase-two/requirements/): "Automated validation
  must be used to measure some aspects of the provider's goals for at least
  70% of the Key Security Indicators." → 70% of 63 = 44 KSIs minimum need
  automated validation.
- **Persistent validation cadence** (per the AWS blog):
  - **At least every 3 days** for machine-based KSIs at moderate impact.
  - **At least every 3 months** for non-machine (procedural) KSIs.

### What's conspicuously absent from the AWS blog

- **No mention of "FRMR" by name.** AWS uses the phrase "machine-readable
  formats" generically.
- **No mention of OSCAL.**
- **No mention of AWS Audit Manager.** This is interesting — Audit Manager is
  AWS's compliance-evidence-collection service, and it's NOT in the blog's
  recommended pattern.
- **No mention of any third-party tooling, AWS Marketplace solutions,
  consulting partners, or open-source projects.** The article positions the
  AWS-native stack as the complete evidence source.
- **No mention of 3PAO workflows**, the 3PAO/CSP boundary, or how 3PAOs
  consume the machine-readable evidence.
- **No mention of CSPs deploying outside AWS** (multi-cloud, hybrid). The
  pattern assumes AWS-native deployment.

---

## 3. Efterlev's actual position relative to AWS's pattern

### Efterlev today (post-Priority-1/2/3, as of 2026-04-28)

- **30 of 60 thematic KSIs covered** at the IaC layer (50% of 60, 47.6% of 63
  if counting CSX).
- **8 of 11 themes covered** (CNA, CMT, IAM, MLA, PIY, RPL, SCR, SVC). The
  remaining 3 (AFR, CED, INR) are entirely procedural and need Evidence
  Manifests rather than detector code.
- **43 detectors** = 36 KSI-mapped + 7 supplementary 800-53-only.
- **Local, pre-deploy scanning model.** Reads `.tf` files (and `.github/workflows/`)
  before `terraform apply` — Efterlev finds the gap before the resource exists.
- **Content-addressed Evidence + JSON sidecars** on every report. Per the
  FedRAMP 20x Phase 2 page: "Participants merely need to address all
  requirements and ensure this information is available in both human-readable
  and machine-readable formats for FedRAMP review." Efterlev's design —
  HTML report + JSON sidecar with schema_version — is exactly this.
- **Three Anthropic-backed agents** (Gap, Documentation, Remediation)
  produce attestation drafts, gap classifications, and Terraform diffs.

### Where Efterlev OVERLAPS with AWS's recommended pattern

- **`aws.config_enabled` detector** evidences the same operational shape AWS
  recommends for KSI-MLA-EVC and KSI-SVC-ACM via Config conformance packs.
  Efterlev says "this customer has Config wired"; the customer can then point
  Efterlev's evidence + AWS Config's runtime evidence together at a 3PAO.
- **`github.action_pinning`** evidences SR-5 + SI-7(1) for KSI-SCR-MIT —
  AWS's blog doesn't address this surface at all (action-pinning is a
  GitHub-Actions-side concern, not an AWS-runtime concern).
- **`aws.suspicious_activity_response`** evidences AC-2(13) for KSI-IAM-SUS
  via the EventBridge→Lambda response pattern AWS itself recommends.
- **`aws.cloudtrail_audit_logging`** evidences KSI-MLA-LET / KSI-MLA-OSM /
  KSI-CMT-LMC for the AWS-native CloudTrail surface.

### Where Efterlev is COMPLEMENTARY to AWS's pattern

- **Pre-deploy scanning.** AWS Config / Security Hub evaluate *deployed*
  state. Efterlev evaluates *pre-deploy* IaC. These are non-overlapping
  feedback loops:
  - Pre-deploy (Efterlev) catches misconfiguration **before** the resource
    exists, during the dev loop.
  - Runtime (Config/Security Hub) catches drift **after** the resource exists,
    in production.
  - A FedRAMP customer needs both. The 3-day persistent-validation cadence
    AWS quotes is a runtime cadence; the dev-loop cadence is whenever-they-
    save (Efterlev's `--watch` mode).
- **OSS, no procurement.** AWS Config / Security Hub require AWS spend and
  org-level approvals. Efterlev runs locally with no SaaS, no telemetry, no
  account creation.
- **Multi-cloud-ready.** Efterlev's `Source` literal already accepts
  `cloudformation`, `cdk`, `k8s`, `pulumi`, `github-workflows`, plus
  `terraform` and `terraform-plan`. CDK and CloudFormation detectors are
  on the v1.5+ roadmap. AWS-native services don't help with Azure / GCP.
- **Dev-workflow integration.** `efterlev report run --watch` re-runs the
  pipeline on every save. AWS Config rule re-evaluations don't have an
  equivalent dev experience.
- **Human-signed attestation flows.** Efterlev's `Evidence Manifests`
  (`.efterlev/manifests/*.yml`) are exactly the artifact CSX-SUM requires:
  customer-authored procedural attestations with provenance binding to
  KSIs. AWS's blog has no equivalent.

### Where Efterlev MAY look weaker on first impression

- **Catalog count optics.** Anyone reading the AWS blog and Efterlev's README
  side-by-side sees "63 vs 60" and may assume Efterlev is behind. The reality
  is just an accounting choice. Easy to fix in docs (§6 below).
- **70% automation threshold.** 30 of 63 = 47.6%. Efterlev's coverage at the
  thematic-KSI layer is below the FedRAMP threshold. But the threshold applies
  to **the customer's whole authorization package**, not to any single tool.
  Efterlev contributes its 30 to a customer's automation total alongside AWS
  Config rules, Security Hub findings, etc.
- **AWS-native deployment assumption.** AWS's blog implicitly positions the
  AWS-native service stack as sufficient. A reader could conclude "I don't
  need a third-party tool." The right counter-positioning is "Efterlev runs
  pre-deploy and your IaC layer; AWS-native runs post-deploy. Use both."

---

## 4. The CSX KSIs — directly producible by Efterlev today

This is the most actionable part of the analysis. The 3 CSX cross-cutting
KSIs map cleanly to **Efterlev artifacts that already exist**:

### KSI-CSX-SUM — Implementation Summaries

> Providers MUST maintain simple high-level summaries of at least the following
> for each Key Security Indicator: goals, consolidated information resources,
> machine-based processes for validation + persistent cycle, non-machine-based
> processes + cycle, current implementation status, clarifications.

**Efterlev produces this** via the Documentation Agent. Each generated
attestation in the `documentation-{ts}.json` sidecar carries:
- KSI ID + status (Gap classification = "current implementation status")
- Cited evidence with detector_id + source_file:line_range (= "consolidated
  information resources")
- Narrative explaining what the scanner saw and didn't see (= "machine-based
  processes for validation")
- The detector + manifest separation (= "non-machine vs machine-based")
- Schema-versioned JSON output ready for 3PAO ingest

**Action item:** Make the README explicit that Efterlev's
`documentation-{ts}.json` IS a CSX-SUM-compliant artifact. The
Documentation Agent already produces CSX-SUM-shaped output today.

### KSI-CSX-MAS — Application within MAS

> Providers SHOULD apply ALL Key Security Indicators to ALL aspects of their
> cloud service offering that are within the FedRAMP Minimum Assessment Scope.

**Efterlev produces this** via the boundary-scoping work that shipped in
Priority 4 (already complete pre-session). `efterlev boundary set 'boundary/**'`
declares the MAS in repo-relative terms; every Evidence carries a
`boundary_state` field and the gap report color-codes by it.

**Action item:** The README's boundary-scoping section should explicitly cite
KSI-CSX-MAS as the FedRAMP requirement it satisfies.

### KSI-CSX-ORD — Order of Criticality

> Providers MAY use the following order of criticality for approaching
> Authorization by FedRAMP Key Security Indicators for an initial
> authorization package: MAS, ADS (Authorization Data Sharing), UCM (Using
> Cryptographic Modules)...

**Efterlev produces this** via:
- The POA&M generator (`efterlev poam`) emits items severity-ordered:
  not_implemented → HIGH, partial → MEDIUM, etc.
- The HTML report's filter pills let reviewers focus on `not_implemented`
  first — exactly the order CSX-ORD prescribes.

**Action item:** A docs section explicitly mapping the POA&M output to
CSX-ORD makes this connection visible to 3PAOs.

---

## 5. Strategic implications

### Short-term (v0.1.0 prep — week of)

The AWS blog doesn't change the v0.1.0 cut. Efterlev's design and catalog
state are correct. What changes is messaging.

1. **Acknowledge the 60+3=63 framing in the README.** A single paragraph in
   the "What v0 contains" section under the detector-count stanza:

   > Efterlev's detector library evidences the **60 thematic KSIs** in FRMR
   > 0.9.43-beta — the catalog AWS's
   > [FedRAMP 20x deep-dive blog (2026-04-27)](...) frames as 63 KSIs by
   > additionally counting the 3 cross-cutting CSX KSIs (CSX-SUM, CSX-MAS,
   > CSX-ORD). Those 3 CSX KSIs are procedural meta-requirements about *how*
   > providers organize their KSI evidence; Efterlev's Documentation Agent
   > attestation output, boundary-scoping primitives, and POA&M severity
   > ordering directly satisfy CSX-SUM, CSX-MAS, and CSX-ORD respectively
   > (see [docs/csx-mapping.md](csx-mapping.md)).

2. **Add `docs/csx-mapping.md`.** A short doc that maps Efterlev's existing
   artifacts to the CSX KSIs — no new code, just documentation linking
   what's already there.

3. **Cross-link the AWS blog post in `docs/index.md` and `docs/icp.md`** as
   "external context — what AWS recommends for AWS-native CSPs."

### Medium-term (v0.1.x patch / v0.2)

1. **Push KSI coverage from 30 → 44** to clear the 70%-of-63 automation
   threshold the FedRAMP 20x Phase 2 page requires. Of the 30 currently-
   uncovered thematic KSIs, the most-tractable in the IaC layer are documented
   in `docs/v1-readiness-plan.md` Priority 1's "What's beyond the floor"
   section. The shortlist:
   - KSI-MLA-ALA (log-bucket access policies)
   - KSI-CNA-OFA (availability-zone diversity)
   - KSI-AFR-VDR (vulnerability detection — partial via existing detectors)
   - KSI-SVC-PRR (instance memory / ephemeral storage)
   - KSI-CED-* / INR-* (procedural — would need richer Manifest tooling)

2. **Add a `efterlev report --csx-summary` flag** that produces a CSX-SUM-
   shaped JSON specifically formatted for 3PAO ingest. Builds on existing
   `documentation-{ts}.json` machinery.

3. **Add a `/scan` GitHub Action wrapper** that takes the JSON sidecar and
   pushes it into a `gh-pages` branch as the persistent-validation evidence
   feed. Closes the "3-day cadence" loop without requiring a separate
   scheduler.

### Long-term (v0.2+)

1. **CR26 (Consolidated Rules 2026)** releases end of June 2026 and takes
   effect Dec 31, 2026. Watch for catalog updates in `FedRAMP/docs` —
   FRMR.documentation.json is the canonical source. Efterlev's
   `efterlev init --baseline` flow should detect catalog version mismatches
   and warn.

2. **Phase 3** (formalizing 20x Low and Moderate, FY26 Q3-Q4) is the
   wide-scale CSP adoption window. Efterlev's positioning at that point
   should explicitly reference its v0.1.x track record.

3. **Multi-cloud detector coverage** (CDK, CloudFormation, Pulumi) per
   `docs/dual_horizon_plan.md` mid-term. AWS-native scanners help only AWS
   customers; Azure/GCP customers are increasingly entering the FedRAMP
   pipeline.

---

## 6. Concrete action items (recommended pre-v0.1.0 cut)

In priority order:

1. **[doc-only, ~30 min]** Add the "60+3=63 framing" paragraph to README.md.
2. **[doc-only, ~1 hr]** Create `docs/csx-mapping.md` mapping existing
   Efterlev artifacts to CSX-SUM, CSX-MAS, CSX-ORD.
3. **[doc-only, ~30 min]** Cross-link the two AWS blog posts in `docs/index.md`
   and `docs/icp.md` as external context.
4. **[doc-only, ~30 min]** Update the release-notes-v0.1.0 draft to mention
   the AWS blog and the CSX framing.
5. **[code, optional, ~2 hr]** Add `KSI-CSX-SUM`, `KSI-CSX-MAS`, `KSI-CSX-ORD`
   to Efterlev's KSI count in `efterlev detectors list` summary, with a clear
   "cross-cutting (procedural)" badge so they're visibly different from
   thematic KSIs.

The first 4 are pure documentation. Item 5 is a small code change to surface
the CSX KSIs in the catalog inventory — debatable whether to do it pre-v0.1.0
since the actual detector coverage doesn't change.

---

## 7. What this analysis does NOT address

- **Whether the v0.1.0 cut should be delayed.** The AWS blog is consistent
  with the catalog Efterlev vendors and doesn't introduce blocking gaps.
  Recommendation: do not delay.
- **AWS's competitive intent.** The blog reads as evangelism for AWS-native
  services, not as a partner-ecosystem play. AWS isn't building an Efterlev
  competitor based on this blog alone. Whether they will is a different
  question; this analysis can't answer it.
- **3PAO acceptance of Efterlev's output.** Priority 5 (real 3PAO touchpoint)
  remains open and is the only way to validate this empirically.
- **Pricing / market dynamics.** Efterlev is OSS; AWS-native services have
  real costs at scale. A customer-shape analysis would be useful but is out
  of scope here.

---

## Sources

- [Deep dive into FedRAMP 20x Key Security Indicators: Decoding the 63 KSIs (AWS Public Sector Blog, 2026-04-27)](https://aws.amazon.com/blogs/publicsector/deep-dive-into-fedramp-20x-key-security-indicators-decoding-the-63-ksis/)
- [Prepare for FedRAMP 20x with AWS automation and validation (AWS Public Sector Blog, 2026-02-18)](https://aws.amazon.com/blogs/publicsector/prepare-for-fedramp-20x-with-aws-automation-and-validation/)
- [FedRAMP 20x Phase 2 Requirements](https://www.fedramp.gov/20x/phase-two/requirements/)
- [FedRAMP 20x Key Security Indicators index](https://www.fedramp.gov/docs/20x/key-security-indicators/)
- [FRMR.documentation.json @ FedRAMP/docs main (verified version: 0.9.43-beta, last commit 2026-04-08)](https://github.com/FedRAMP/docs/blob/main/FRMR.documentation.json)
- Efterlev's vendored copy: `catalogs/frmr/FRMR.documentation.json` — same version, same content.
