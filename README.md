# Efterlev

**Open-source compliance automation for SaaS companies pursuing their first FedRAMP Moderate authorization via the FedRAMP 20x pilot.**

Scans your Terraform for KSI-level evidence. Drafts FRMR-compatible validation data for your 3PAO. Proposes code-level remediations you can apply today. Runs locally — no SaaS, no telemetry, no procurement cycle.

Built for the VP Eng or DevSecOps lead whose CEO just told them "we need FedRAMP" and who needs to know, by Monday, where they actually stand.

Pronounced "EF-ter-lev." From Swedish *efterlevnad* (compliance).

```bash
pipx install efterlev
cd your-repo
efterlev init --baseline fedramp-20x-moderate
efterlev scan
```

Efterlev is **KSI-native**: its primary abstraction is the Key Security Indicator from FedRAMP 20x, with 800-53 Rev 5 controls as the underlying reference. Its primary output is **FRMR-compatible JSON** (the format FedRAMP 20x is standardizing on). OSCAL output for users transitioning Rev5 submissions is on the v1 roadmap.

Efterlev's current focus is SaaS companies pursuing their first FedRAMP Moderate authorization. Defense contractors pursuing CMMC 2.0 or DoD IL are a v1.5+ expansion; platform teams at larger gov-contractors are v2+. See [docs/icp.md](./docs/icp.md) for the full user profile and what that means for what Efterlev does and doesn't do.

---

## What it does

- **Scans** Terraform source for evidence of FedRAMP 20x Key Security Indicators (KSIs), backed by the underlying NIST 800-53 Rev 5 controls those KSIs reference
- **Drafts** FRMR-compatible attestation JSON grounded in that evidence, with every assertion citing its source line
- **Proposes** code-level remediation diffs for detected gaps
- **Emits** machine-readable validation data ready for 3PAO review and the FedRAMP 20x automated validation pipeline
- **Traces** every generated claim back to the source line that produced it

Everything runs locally. The only outbound network call is to your configured LLM endpoint for reasoning tasks (narrative drafting, remediation proposals). Scanner output is deterministic and offline.

## What it doesn't do

- It does not produce an Authorization to Operate. Humans and 3PAOs do that.
- It does not certify compliance. It produces drafts that accelerate the human review cycle.
- It does not guarantee generated narratives are correct. Every LLM-generated artifact is marked "DRAFT — requires human review."
- It does not cover SOC 2, ISO 27001, HIPAA, or GDPR. Other tools serve those well; see [COMPETITIVE_LANDSCAPE.md](./COMPETITIVE_LANDSCAPE.md) for the landscape.
- It does not scan live cloud infrastructure yet. v1.

See [LIMITATIONS.md](./LIMITATIONS.md) for the honest full accounting.

---

## Why it exists

A 100-person SaaS company just got told by its biggest prospect: "we'll buy, but only if you're FedRAMP Moderate by next year."

The team looks at each other. Nobody has done this before. They google it and find:

- Consulting engagements starting at $250K
- SaaS compliance platforms that cover SOC 2 beautifully but treat FedRAMP as a footnote
- Enterprise GRC tooling priced for the wrong scale
- Spreadsheets, Word templates, and a NIST document family that runs to thousands of pages

What they actually need is something that reads their Terraform and tells them, in their own language, what's wrong and how to fix it. Something a single engineer can install on a Tuesday and show results at Wednesday's standup. Something whose output is concrete enough that their 3PAO can use it — and whose claims are honest enough that the 3PAO won't throw it out.

Efterlev is that tool. It runs where the engineer already is (the repo, the CLI, the CI pipeline). It produces FRMR from day one — the machine-readable format FedRAMP 20x is standardizing on, and the format most new SaaS authorizations in 2026 will target — with OSCAL support on the v1 roadmap for users carrying Rev5 transition submissions. It refuses to overclaim because 3PAOs don't trust tools that do.

As of April 2026, FedRAMP 20x Phase 2 Moderate pilot is still active past its original March 31, 2026 end date, with authorizations like Aeroplicity's landing as recently as April 13, and wider public rollout targeted for later in 2026 — the trajectory Efterlev's KSI-native posture is aligned with.

It's also deliberately deep rather than broad. FedRAMP 20x Moderate first; DoD IL and CMMC 2.0 on the v1 roadmap. Not SOC 2, not ISO 27001, not HIPAA — there are tools that serve those well, and our value is depth in gov-grade frameworks, not breadth across every compliance acronym.

Add [COMPETITIVE_LANDSCAPE.md](./COMPETITIVE_LANDSCAPE.md) to see where Efterlev fits among existing tools.

---

## Quickstart

### Install

```bash
pipx install efterlev
```

Requires Python 3.12+. `uv` is used internally but not required for end users.

### Configure

```bash
cd path/to/your-repo
efterlev init --baseline fedramp-20x-moderate
```

This creates a `.efterlev/` directory for the local provenance store and writes a config file. The FedRAMP FRMR KSI baseline and the NIST 800-53 Rev 5 catalog are shipped with Efterlev (vendored under `catalogs/`); no network fetch is required at init time.

You'll need an Anthropic API key for the generative agents (narrative drafting, remediation). Set `ANTHROPIC_API_KEY` in your environment or configure it in `.efterlev/config.toml`.

### Scan

```bash
efterlev scan
```

Runs all applicable detectors against your Terraform and source. Produces findings with full provenance. Scanner-only — no LLM calls, no network; FRMR and 800-53 catalogs are loaded from the local `catalogs/` directory.

### Analyze

```bash
efterlev agent gap
```

The Gap Agent classifies each KSI as implemented, partially implemented, not implemented, or not applicable, given the evidence collected. Underlying 800-53 control status is shown alongside. Writes a human-readable HTML report to `out/gap_report.html`.

### Draft FRMR attestation

```bash
efterlev agent document --ksi KSI-SVC-VRI
```

The Documentation Agent drafts FRMR-compatible attestation JSON for a KSI, grounded in its evidence. Every assertion cites the evidence that supports it. Output is an HTML rendering alongside the FRMR JSON. OSCAL SSP narrative generation is a v1 roadmap item for users carrying Rev5 transition submissions.

### Propose remediation

```bash
efterlev agent remediate --ksi KSI-SVC-VRI
```

The Remediation Agent proposes a code-level diff to address a gap. Review the diff, then apply it yourself or hand it to Claude Code.

### Walk the provenance

```bash
efterlev provenance show <claim_id>
```

Every generated claim traces back to the evidence that produced it and the source line that produced that. If the chain doesn't resolve, the claim is weak.

---

## Current coverage

### Input sources (v0)

Efterlev v0 scans **Terraform and OpenTofu** source files (`.tf`). It does not scan CloudFormation, AWS CDK, Pulumi, Kubernetes manifests, or live cloud infrastructure. Each of those is on the v1 roadmap below.

If your FedRAMP boundary is Terraform-primary, Efterlev works for you today. If you're deep in CloudFormation or CDK, hold off — v1 is not far.

### FedRAMP 20x KSIs and underlying 800-53 controls (v0)

KSIs below are from FRMR 0.9.43-beta (vendored at `catalogs/frmr/`). Each detection area evidences the listed KSI(s) and the 800-53 controls the KSI references.

| Detection area | KSI (FRMR 0.9.43-beta) | 800-53 | Source |
|---|---|---|---|
| Encryption at rest | `[TBD]` — see note below; closest fit is **KSI-SVC-VRI** (Validating Resource Integrity) | SC-28, SC-28(1) | Terraform/OpenTofu (S3, RDS, EBS) |
| Transmission confidentiality | **KSI-SVC-SNT** (Securing Network Traffic) | SC-8 | Terraform/OpenTofu (ALB, TLS) |
| Cryptographic protection | **KSI-SVC-VRI** (Validating Resource Integrity); reinforces KSI-SVC-SNT | SC-13 | Terraform/OpenTofu, source |
| MFA enforcement | **KSI-IAM-MFA** (Enforcing Phishing-Resistant MFA) | IA-2 | Terraform/OpenTofu (IAM policy conditions) |
| Event logging & audit generation | **KSI-MLA-LET** (Logging Event Types), **KSI-MLA-OSM** (Operating SIEM Capability) | AU-2, AU-12 | Terraform/OpenTofu (CloudTrail) |
| System backup | **KSI-RPL-ABO** (Aligning Backups with Objectives) | CP-9 | Terraform/OpenTofu (RDS, S3 versioning) |

> **Note on SC-28.** FRMR 0.9.43-beta does not list SC-28 in any KSI's `controls` array, so no KSI cleanly maps to "encryption of data at rest." KSI-SVC-VRI (integrity via cryptography) is the nearest fit in the Service Configuration theme, whose description references "FedRAMP encryption policies." We treat this as a known mapping gap: the detector will be honest in its README that it evidences the infrastructure layer of at-rest encryption but cannot claim full alignment with a KSI that does not explicitly cover confidentiality-at-rest. This is the kind of gap we expect to see resolved as FRMR moves from beta toward GA.

> **Note on KSI-IAM-MFA.** The indicator requires *phishing-resistant* MFA. Our detector evidences that MFA is enforced via IAM policy condition keys, which is MFA presence but not phishing resistance. The detector README calls this out explicitly.

Every detector's `README.md` inside `src/efterlev/detectors/` names what it proves and what it does not prove. Read those before trusting a finding.

### On the roadmap

Expansion happens along two axes in parallel: **input sources** (what Efterlev can scan) and **KSI / control coverage** (what it can find). Source-type expansion matters more for adoption; coverage expansion matters more for depth.

- **Month 1:** Terraform Plan JSON support (scans resolved plans including computed values); OpenTofu declared as first-class alongside Terraform; **OSCAL output generators** for users transitioning Rev5 submissions (Assessment Results, partial SSP, POA&M) — this is the primary deliverable beyond the KSI-native v0
- **Month 1–2:** +15 detectors for Terraform covering additional KSIs in the IAM, CMT, MLA, and SVC themes; AWS Bedrock as a second LLM backend for FedRAMP-authorized deployments (GovCloud)
- **Month 2:** CloudFormation and AWS CDK support (CDK compiles to CloudFormation; one parser covers both)
- **Month 3:** First external contributor detector merged; Kubernetes manifests + Helm (network policies, pod security, RBAC — different control set, high value)
- **Month 4:** GitHub Action for PR-level compliance checks; Pulumi support
- **Month 5:** CMMC 2.0 overlay
- **Month 6:** Drift Agent — watches a repo over time, flags regressions in evidenced KSIs
- **v1.5+:** Runtime cloud API scanning (different threat model, needs its own design pass)

See [docs/dual_horizon_plan.md](./docs/dual_horizon_plan.md) for the full roadmap.

---

## How it works

Three concepts. Everything else is implementation detail.

**Detectors** read source material (Terraform plans, app code, CI configs) and emit deterministic evidence. They are the moat: a community-contributable library where each detector is a self-contained folder.

**Primitives** are typed, MCP-exposed functions that represent agent-legible capabilities — scan, map, generate, validate. ~15–25 of them, small and stable. Both our own agents and external agents (your own Claude Code session, for instance) can call them.

**Agents** compose primitives to accomplish a reasoning task: classifying KSI gap status, drafting FRMR attestations, proposing remediation. Each agent has a system prompt you can read in the repo and a typed output artifact you can audit.

Every step emits a provenance record. The provenance store is a content-addressed, append-only graph — scanner output is evidence, agent output is a claim derived from that evidence, and you can walk the chain from any generated sentence back to the Terraform line that produced it.

The architectural bet: evidence before claims, provenance always, KSIs as the user-facing surface, FRMR as primary output (OSCAL in v1 for users who need it). See [docs/architecture.md](./docs/architecture.md) for details.

---

## Integrating with Claude Code

Efterlev exposes its primitives via an MCP server. Point any Claude Code session at it and Claude can discover and call every primitive directly.

```bash
efterlev mcp serve
```

In your Claude Code settings, add the server. Claude can now scan your repo, walk provenance, draft narratives, or propose remediations as part of a broader coding session — the same capabilities Efterlev's own agents use, available to yours.

This also means: if you want to build a compliance workflow Efterlev doesn't ship, you don't need to fork Efterlev. Write your own agent against the MCP interface.

---

## Project status

**v0.1** — hackathon release. Six detectors, three agents, FedRAMP 20x Moderate only (KSI-native), AWS + Terraform only. Usable for KSI gap analysis and draft FRMR attestation generation; not yet a production workflow.

**Stable surface:** primitive interface, detector contract, provenance model, FRMR output shape. These are designed to not break.

**Changing surface:** detector content (as we add more), agent system prompts (as we tune them), CLI ergonomics (as we hear from users), OSCAL output generators (arriving in v1).

---

## Contributing

We want contributors. The detector library is designed to make the common contribution — "here's a new KSI indicator I can evidence from Terraform" — a self-contained folder that doesn't touch the rest of the codebase.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the five-minute path from `git clone` to running tests, and the hour path from idea to open PR.

Good first issues are labeled `good first issue` on GitHub. The most valuable contributions right now are new detectors covering KSIs on the roadmap.

---

## Governance

Benevolent-dictator model during v0–v1 (the author), with an explicit commitment to move to a technical steering committee at 10 active contributors. See [DECISIONS.md](./DECISIONS.md) for the governance record and [CONTRIBUTING.md](./CONTRIBUTING.md) for how maintainer status works.

This project may be donated to a neutral foundation (OpenSSF, Linux Foundation, CNCF) at maturity if contributor diversity warrants. That decision is not made and not time-boxed.

---

## License and security

Apache 2.0. See [LICENSE](./LICENSE).

Security issues: see [SECURITY.md](./SECURITY.md) for the coordinated disclosure process.

Threat model for Efterlev itself: [THREAT_MODEL.md](./THREAT_MODEL.md).

---

## Credits

Efterlev was bootstrapped in a 4-day hackathon using [Claude Code](https://claude.com/claude-code). The architecture commits to keeping Claude Code (and other MCP-capable agents) as first-class integration partners — that's what "agent-first" means here, structurally, not as marketing.

Built on [compliance-trestle](https://github.com/IBM/compliance-trestle) for OSCAL catalog loading, on the FedRAMP Machine-Readable (FRMR) content published at [FedRAMP/docs](https://github.com/FedRAMP/docs), and on the NIST SP 800-53 Rev 5 catalog published at [usnistgov/oscal-content](https://github.com/usnistgov/oscal-content). Those projects make this one possible.

---

## Documentation

- [docs/icp.md](./docs/icp.md) — the Ideal Customer Profile: who Efterlev is for, how we decide what to build
- [docs/dual_horizon_plan.md](./docs/dual_horizon_plan.md) — full plan and roadmap
- [docs/architecture.md](./docs/architecture.md) — deeper architectural detail
- [LIMITATIONS.md](./LIMITATIONS.md) — what Efterlev does and doesn't do
- [THREAT_MODEL.md](./THREAT_MODEL.md) — security posture
- [COMPETITIVE_LANDSCAPE.md](./COMPETITIVE_LANDSCAPE.md) — honest positioning against Comp AI, RegScale OSCAL Hub, and others
- [DECISIONS.md](./DECISIONS.md) — architectural decision log
- [CONTRIBUTING.md](./CONTRIBUTING.md) — contributor onboarding
