# Competitive Landscape

Honest positioning of Efterlev against adjacent tools. This document exists because hiding from the competition is worse than naming it, and because contributors and potential users deserve a clear answer to "why this instead of that."

This is a first-class document. It is updated as the landscape evolves.

---

## The short version

Efterlev is **not** trying to be:
- "The open-source AI compliance platform." Comp AI (trycompai) occupies that space and has real traction (600+ customers, multi-framework coverage).
- "The OSS OSCAL platform." RegScale donated OSCAL Hub to the OSCAL Foundation in late 2025; that tier is taken.
- A dashboard-driven compliance tool for GRC teams. That market is well-served.

Efterlev **is** trying to be:
- **The KSI-native compliance scanner aligned with FedRAMP 20x.** Primary abstraction is the Key Security Indicator; primary output is FRMR-compatible JSON. No other OSS tool is KSI-native today.
- The repo-native, agent-first scanner for FedRAMP and DoD Impact Levels.
- The tool that lives in the developer's codebase and CI pipeline rather than in a SaaS dashboard.
- The tool that produces code-level findings, remediation diffs, FRMR-compatible validation data (v0), and standards-compliant OSCAL output for downstream consumption (v1).
- Deep, not broad — FedRAMP 20x + DoD IL done well rather than five frameworks at 40–60% coverage each.
- Deployable inside FedRAMP-authorized boundaries via AWS Bedrock in GovCloud (v1) — a path SaaS-first competitors cannot match without their own FedRAMP authorization.

---

## The detailed landscape

### Comp AI (trycompai) — closest overlapping player

Open-source, AI-agent-driven, SaaS-first compliance platform. Covers SOC 2, ISO 27001, HIPAA, GDPR, and FedRAMP across one product. 600+ customers. Ships AI-generated policies, continuous evidence collection from 500+ SaaS integrations, an OSS device agent, cloud monitoring, and a live trust-center feature.

**Where they overlap with Efterlev:** both are OSS, both use AI agents, both list FedRAMP in their supported frameworks.

**Where they don't overlap:**
- Comp AI is SaaS-first with OSS components. Efterlev is local-first with no SaaS at all.
- Comp AI covers FedRAMP at ~41% in their own demo screenshots (listed as one framework among many) and frames it in Rev5 terms. Efterlev's v1 goal is 80%+ of **FRMR-Moderate KSI coverage** — the 20x surface FedRAMP is actually evaluating against today. No major OSS compliance platform is KSI-native yet; Comp AI is not.
- Comp AI does not scan Terraform source. Efterlev does.
- Comp AI does not produce code-level remediation diffs. Efterlev does.
- Comp AI does not emit FRMR-compatible validation data or OSCAL artifacts as primary outputs. Efterlev produces FRMR in v0 and OSCAL in v1.
- Comp AI does not address DoD Impact Levels. Efterlev's v1 roadmap includes IL4/5/6.
- Comp AI's extension model is SaaS integrations. Efterlev's extension model is a community-contributable detector library.

**Who picks which:** a compliance team at a SaaS company doing SOC 2 + ISO 27001 picks Comp AI. A DevSecOps engineer at a defense contractor doing FedRAMP + IL4 picks Efterlev. Different buyer, different locus of work, different depth of focus.

### RegScale OSCAL Hub — OSS OSCAL platform tier

Donated by RegScale to the OSCAL Foundation in late 2025. Positioned as "the industry's first comprehensive, open-source platform purpose-built for working with OSCAL documents." Document processing, review workflows, and authorization-package tooling aimed at Authorizing Officials, the FedRAMP PMO, ISSOs, and 3PAOs.

**Relationship to Efterlev:** complementary, not competitive. In v1, Efterlev will produce OSCAL artifacts that OSCAL Hub can consume and process for users carrying Rev5 transition submissions. A user could run Efterlev against their repo, export the OSCAL output, and submit it through OSCAL Hub's review flow.

**Where they overlap:** both are OSS.

**Where they don't overlap:**
- OSCAL Hub's center of gravity is deep-OSCAL and Rev5-native. Efterlev's center of gravity is KSI-native and FRMR-first — we are where FedRAMP 20x is going, they are where FedRAMP has been. The transition from one to the other is multi-year, so both lanes matter.
- OSCAL Hub is a platform for *reviewing* OSCAL packages. Efterlev is a tool for *producing* validation data (FRMR at v0, OSCAL at v1) from source code.
- OSCAL Hub serves Authorizing Officials and compliance reviewers. Efterlev serves DevSecOps engineers and the compliance team preparing submissions.
- OSCAL Hub does not scan code. Efterlev does not handle authorization workflows.

**Integration possibility:** a supported output path where `efterlev` directly posts OSCAL (once the v1 generator lands) to an OSCAL Hub instance is a plausible v1 feature if demand warrants.

### Dormant or narrow OSS prior art

- **strongdm/comply** — SOC 2-focused policy site generator. Different framework focus. Largely dormant.
- **18F/compliance-toolkit** — OpenControl Masonry era (2015–2017). Inactive.
- **GoComply/fedramp** — Go tool that converts OSCAL documents to FedRAMP Word templates. Narrow scope, no AI, no scanning. Useful as a *consumer* of OSCAL output.
- **mrice/complykit** — 2013-era Maven plugin for license compliance checking. Dormant.
- **ComplianceAsCode / OpenSCAP** — mature rule-based scanner, massive content library, not AI-native, not OSCAL-focused. Useful as a source of content patterns; not competing at the architecture level.

### Commercial SaaS players (not AI-native)

- **Vanta, Drata, Secureframe, Paramify** — SaaS compliance automation platforms. GRC-team-centric. Not OSS. Have shipped AI features in the last 18 months but remain dashboard-first. Efterlev's dev-tool-shaped positioning is different enough that coexistence is reasonable — some customers will use both.
- **RegScale, Xacta, IGNYTE** — enterprise compliance platforms. Deeper in gov than Vanta/Drata. OSCAL-aware. Efterlev does not compete at this tier; Efterlev users might eventually feed Efterlev output into one of these.

### AI-agent-specific security tools

- **AgentAuditKit** — scans AI agent configs (MCP servers, prompt files) for security misconfigurations. Maps findings to EU AI Act, SOC 2, ISO 27001, HIPAA, NIST AI RMF. Different scope (scanning AI agents for security, not scanning infrastructure for compliance), but philosophically adjacent.

---

## The positioning test

For Efterlev to be worth building, it has to answer a specific question with "yes":

> Is there a user for whom the dev-tool-shaped, repo-native, FedRAMP-focused, open-source scanner is the right tool — and who would not be well-served by Comp AI, RegScale, or Vanta?

The answer is yes, and the user is specific. Efterlev's primary ICP is a **SaaS company (50–200 engineers) pursuing its first FedRAMP Moderate authorization** — typically triggered by a federal customer deal contingent on authorization. The work is owned by a DevSecOps lead or senior platform engineer; the urgency comes from the CEO and the revenue on the line. Full profile at [docs/icp.md](./docs/icp.md).

For this user:

- **Comp AI is the wrong depth and the wrong era.** Their FedRAMP coverage (41% in their own demo) reflects their broader SOC 2–first positioning and maps to legacy Rev5 controls. An ICP A user starting FedRAMP in 2026 is heading into 20x, where the KSIs are what matter. Efterlev is KSI-native; Comp AI is not.
- **RegScale is the wrong tier.** Built for Authorizing Officials, ISSOs, and mature compliance organizations, with deep OSCAL infrastructure. An ICP A SaaS company doesn't have that team yet, and is better served by FRMR than by OSCAL for 20x work.
- **Vanta/Drata are the wrong shape.** SaaS dashboards optimized for SOC 2 / ISO 27001; their FedRAMP modules are thinner and their locus is wrong for a single-engineer DevSecOps lead.

Secondary ICPs (defense contractors pursuing CMMC 2.0 / DoD IL; platform teams at larger gov-contractor orgs) are named in `docs/icp.md` as v1.5+ and v2+ expansions. They are well-served by the architecture we're building but are not the v0 focus.

For a SaaS compliance team doing SOC 2 + HIPAA, Comp AI is the right tool. For an Authorizing Official reviewing packages, OSCAL Hub is the right tool. These markets overlap at the edges but have distinct centers of gravity, and this is healthy.

---

## How we will continue to evaluate

This document will be updated:
- When a significant new player enters the OSS compliance-scanning space
- When an existing player's positioning shifts materially (e.g., Comp AI launches a dedicated FedRAMP-focused scanner)
- At every minor release (v0.x → v0.y) as a review checkpoint
- When a user or contributor points out a player we missed

Pull requests that add or update entries here are welcome. Pejorative language about competitors is not welcome; honest assessment is.

---

## Anti-FUD commitment

This document does not:

- Make negative claims about competitors we haven't verified
- Suggest competitors are inadequate where they serve their users well
- Position Efterlev as universally superior — it isn't
- Hide information because it favors a competitor

The goal is useful clarity for users making tool decisions, not marketing against competitors. If you find a statement in this document that crosses that line, file an issue.

---

*Last reviewed: repo creation. Update this date with every review.*
