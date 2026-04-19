# Limitations

Efterlev is useful. It is also bounded in specific ways. This document names those bounds honestly, because compliance tooling that overclaims is worse than compliance tooling that's modest about its scope.

**This is a first-class document, not a disclaimer.** It is updated alongside feature work, not at release time.

---

## What Efterlev does not do

### It does not produce an Authorization to Operate (ATO)

Efterlev produces drafts, findings, and evidence. The authorization decision is made by a human Authorizing Official after review by a 3PAO (for FedRAMP) or an authorized assessor (for DoD IL). No tool — AI-powered or otherwise — produces an ATO.

### It does not certify compliance

An Efterlev scan that finds no gaps does not mean the system is compliant with the target framework. It means the controls Efterlev can detect show no gaps. The controls Efterlev does not detect (policy, procedural, human-process) are unaddressed by the tool.

### It does not replace a 3PAO or an assessor

Efterlev accelerates the draft-and-review cycle. It does not substitute for independent assessment. LLM-generated narratives are drafts, marked as drafts, and require human review before submission to any authorizing body.

### It does not guarantee the accuracy of generated content

Generated content — FRMR attestations, KSI mappings, SSP narratives (v1), remediation proposals — is produced by large language models. Models hallucinate. Efterlev's provenance system mitigates hallucination by forcing every generated claim to cite its underlying evidence, but it does not eliminate it. Every Claim in the system carries a "DRAFT — requires human review" marker for this reason.

### It does not scan live cloud infrastructure (at v0)

Efterlev v0 reads Terraform and OpenTofu source files (`.tf`). It does not call AWS, Azure, or GCP APIs to inspect running resources. CloudFormation, AWS CDK, Pulumi, and Kubernetes manifests are v1 additions — see the roadmap in `README.md`. Runtime cloud API scanning is v1.5+.

### It does not perform continuous monitoring (at v0)

Efterlev runs on demand (locally or in CI). It does not run as a daemon watching for drift. The provenance graph's append-only, versioned structure is designed to support continuous monitoring in v1, but the monitoring daemon itself is not yet built.

### It does not cover the full FedRAMP 20x Moderate KSI set (at v0)

The hackathon MVP covers six detection areas (encryption at rest, transmission confidentiality, cryptographic protection, MFA enforcement, event logging & audit generation, system backup) for which infrastructure-layer evidence is genuinely dispositive. FRMR 0.9.43-beta defines 60 KSIs across 11 themes (backed by 800-53 Rev 5 controls — the full Moderate baseline has ~323 controls plus enhancements). The rest will be added incrementally in v1+. See `README.md` for the current coverage table.

### The FRMR KSI ↔ 800-53 mapping has known gaps

FRMR is at version 0.9.43-beta as of the vendored snapshot. Some 800-53 controls we can genuinely detect do not yet map to any KSI — most notably SC-28 (encryption at rest). Where this happens, Efterlev will evidence the underlying control honestly and flag the KSI mapping as `[TBD]` or use the closest thematic fit with an explicit caveat in the detector's README. We do not invent KSIs that do not exist in the vendored FRMR, and we do not claim clean KSI alignment where one does not exist.

### It does not detect policy, procedural, or human-process controls

Controls like AT-* (Awareness and Training), PL-* (Planning), PS-* (Personnel Security), PM-* (Program Management), and large parts of AC-* (Access Control — the procedural aspects) cannot be detected from code and IaC alone. Efterlev can generate draft narratives for these controls and their related KSIs (the CED and PIY themes, for example, are heavily procedural), but it cannot provide evidence of their implementation.

### It does not cover frameworks beyond FedRAMP and DoD IL (at v0)

CMMC 2.0 is the planned v1 second framework (same 800-171 base, different overlay). SOC 2, ISO 27001, HIPAA, PCI-DSS, GDPR are explicitly out of scope — other tools (Comp AI, Vanta, Drata) serve those frameworks well, and Efterlev's focus on gov-grade frameworks is deliberate.

### It does not create real pull requests (at v0)

The Remediation Agent produces code diffs as local output. Opening PRs against remote repositories is a v1+ capability; the hackathon demo shows the diff, not a pushed commit.

---

## Known limitations in what Efterlev does do

### Detector coverage is partial by design

Each detector's `README.md` states what the detector proves and what it does not prove. For example: the SC-28 S3 encryption detector evidences the infrastructure layer of SC-28 (encryption is configured) but does not evidence the procedural layer (key management practices, rotation policies, BYOK). Never read an Efterlev finding as "SC-28 is implemented"; read it as "infrastructure-layer evidence for SC-28 is present."

### FRMR output validation is schema-level, not semantic

Efterlev validates generated FRMR against `FedRAMP.schema.json` (vendored at `catalogs/frmr/`). It does not validate against any additional submission-time constraints FedRAMP may apply during the 20x authorization review. Schema-valid FRMR from Efterlev may still require refinement before submission.

### OSCAL output (v1) validation is schema-level, not semantic

When the v1 OSCAL generators ship, generated OSCAL will be validated against the NIST schemas. It will not be validated against FedRAMP's stricter Rev5 submission requirements, which include additional constraints the base OSCAL schema does not express. Schema-valid OSCAL from Efterlev may still require refinement before FedRAMP submission.

### Generated narratives reflect the evidence we have, not the narrative the reviewer expects

LLM-drafted SSP narratives are grounded in the evidence records Efterlev has collected. If the evidence is thin, the narrative will be thin. The Documentation Agent does not invent implementation details to fill gaps; it describes what is evidenced and flags what is not.

### Confidence levels are heuristic

Claims carry confidence levels (`low` / `medium` / `high`). These are heuristic, not statistically calibrated. They reflect model signal on narrative specificity and evidence density, not a measured probability of correctness.

### The tool itself is not FedRAMP-authorized

Efterlev is a developer tool that runs locally or in CI. It is not an authorized cloud service. Using Efterlev does not confer any authorization status on the user's system.

---

## How to read Efterlev output responsibly

1. **Findings are evidence, not conclusions.** An Efterlev finding that SC-28 has infrastructure-layer evidence is a starting point for a compliance review, not the review itself.
2. **Claims require human review.** Every LLM-generated artifact is marked "DRAFT." Do not submit Efterlev-generated SSP narratives to a 3PAO without human review.
3. **Walk the provenance chain.** Every generated sentence can be traced back to the evidence that produced it. If the chain doesn't resolve or the evidence is thin, the sentence is weak.
4. **Treat coverage gaps as coverage gaps.** Controls Efterlev did not detect are not controls that are absent; they are controls Efterlev did not look for. Separate tools or manual review cover the rest.

---

## Where we are honest and where we are aspirational

**Honest today:**
- Every claim in this document is true at time of writing.
- Every feature described in `README.md` is implemented and tested.
- The provenance chain is walkable for every generated claim.

**Aspirational / roadmap:**
- Broader control coverage (tracked in GitHub milestones)
- Continuous monitoring
- Real PR creation
- CMMC 2.0 overlay
- Cloud API scanning
- Runtime agent

The distinction is maintained in `README.md`: features that are shipped vs. features on the roadmap.

---

## Reporting a limitation we haven't named

If you find a case where Efterlev overclaims, underdelivers, or produces misleading output, file an issue. Honest limitations are a product feature; undocumented ones are a bug.
