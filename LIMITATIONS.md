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

### It does not scan live cloud infrastructure (at v0 or v1)

Efterlev reads Terraform and OpenTofu source files (`.tf`) and customer-authored attestation manifests (`.efterlev/manifests/*.yml`). It does not call AWS, Azure, or GCP APIs to inspect running resources. Per the v1 scope lock (`DECISIONS.md` 2026-04-22): CloudFormation, AWS CDK, Pulumi, Kubernetes manifests, and runtime cloud API scanning are deferred to v1.5+, gated on customer pull.

### It does not perform continuous monitoring (at v0)

Efterlev runs on demand (locally or in CI). It does not run as a daemon watching for drift. The provenance graph's append-only, versioned structure is designed to support continuous monitoring in v1, but the monitoring daemon itself is not yet built.

### It does not cover the full FedRAMP 20x Moderate KSI set via detectors alone

Six scanner-visible detection areas ship (encryption at rest, transmission confidentiality, cryptographic protection, MFA enforcement, event logging & audit generation, system backup) — the areas where infrastructure-layer Terraform evidence is genuinely dispositive. FRMR 0.9.43-beta defines 60 KSIs across 11 themes; most of the remainder are procedural and cannot be evidenced from code alone. For those, v1 Phase 1 (Evidence Manifests, landed 2026-04-22) is the complement: customers author signed attestations under `.efterlev/manifests/*.yml` and those records flow into the Gap Agent alongside detector Evidence. Scanner-only coverage is ~20% of the baseline; scanner + manifests can approach 80%+ when customers author the procedural attestations their organization can genuinely sign for. Additional detectors for the scanner-visible layer (Phase 6 target: 30 total) are held pending customer signal per the v1 lock.

### The FRMR KSI ↔ 800-53 mapping has known gaps

FRMR is at version 0.9.43-beta as of the vendored snapshot. Some 800-53 controls we can genuinely detect do not yet map to any KSI — most notably SC-28 (encryption at rest). Where this happens, Efterlev will evidence the underlying control honestly and flag the KSI mapping as `[TBD]` or use the closest thematic fit with an explicit caveat in the detector's README. We do not invent KSIs that do not exist in the vendored FRMR, and we do not claim clean KSI alignment where one does not exist.

### It does not automatically detect policy, procedural, or human-process controls

Controls like AT-* (Awareness and Training), PL-* (Planning), PS-* (Personnel Security), PM-* (Program Management), and large parts of AC-* (Access Control — the procedural aspects) cannot be detected from code and IaC alone. v1 Phase 1 Evidence Manifests are the path: customers declare what their organization does and who signed off (a VP, a security lead, a runbook owner) in a YAML the same way they commit code. The Gap Agent sees those attestations and classifies KSIs accordingly. What Efterlev does NOT do is evidence the underlying human process; it captures the attestation and its review cadence (`next_review` date), and the tool's output makes clear the record is human-signed, not machine-verified. A reviewer or 3PAO still evaluates the underlying process.

### It does not cover frameworks beyond FedRAMP and DoD IL (at v0)

CMMC 2.0 is the planned v1 second framework (same 800-171 base, different overlay). SOC 2, ISO 27001, HIPAA, PCI-DSS, GDPR are explicitly out of scope — other tools (Comp AI, Vanta, Drata) serve those frameworks well, and Efterlev's focus on gov-grade frameworks is deliberate.

### It does not create real pull requests (at v0)

The Remediation Agent produces code diffs as local output. Opening PRs against remote repositories is a v1+ capability; the hackathon demo shows the diff, not a pushed commit.

---

## Known limitations in what Efterlev does do

### Detector coverage is partial by design

Each detector's `README.md` states what the detector proves and what it does not prove. For example: the SC-28 S3 encryption detector evidences the infrastructure layer of SC-28 (encryption is configured) but does not evidence the procedural layer (key management practices, rotation policies, BYOK). Never read an Efterlev finding as "SC-28 is implemented"; read it as "infrastructure-layer evidence for SC-28 is present."

### FRMR attestation output is Pydantic-validated, not FedRAMP-schema-validated

The FRMR attestation JSON artifact (`efterlev agent document` output) is validated against the Pydantic `AttestationArtifact` model at construction time — `extra="forbid"`, strict literal types, `requires_review=Literal[True]`. FedRAMP's vendored `FedRAMP.schema.json` describes the FRMR *catalog* (what KSIs exist), not attestation *output* (a CSP's statement of evidence). FedRAMP has not published an attestation-output schema as of April 2026; when they do, Efterlev will migrate. See `DECISIONS.md` 2026-04-22 "Phase 2: FRMR attestation generator" for the full schema-posture call. Regardless of schema validation, submission-time FedRAMP review may apply additional constraints the tool does not capture — the artifact is a draft, always.

### OSCAL output is deferred to v1.5+

The v1 scope lock (2026-04-22) moved OSCAL SSP / AR / POA&M generators from v1 to v1.5+, gated on customer pull. The internal data model already supports serialization into OSCAL shapes when needed; the generators are not built. Rev5-transition users and RegScale OSCAL-Hub-consuming prospects are the signal that pulls them forward.

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
