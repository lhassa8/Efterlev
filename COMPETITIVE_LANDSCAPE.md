# Competitive Landscape

Honest positioning of Efterlev against adjacent tools. This document exists because hiding from the competition is worse than naming it, and because contributors and potential users deserve a clear answer to "why this instead of that."

This is a first-class document. It is updated as the landscape evolves.

---

## The short version

**April 2026 reality update:** Paramify cleared FedRAMP 20x Phase 2 Moderate authorization during the pilot and now markets "authorization in under 30 days" as a case-study-backed claim. compliance.tf is shipping a direct technical-substitute product (185 FedRAMP Moderate controls enforced at Terraform module-download time; scan/edit/enforce rules in Q2 2026). AWS has published a first-party "Prepare for FedRAMP 20x" automation blog. The landscape tightened considerably between the initial writeup of this document and 2026-04-23; sections below are updated to reflect that.

Efterlev is **not** trying to be:
- "The open-source AI compliance platform." Comp AI (trycompai) occupies that space and has real traction (600+ customers, multi-framework coverage).
- "The OSS OSCAL platform." RegScale donated OSCAL Hub to the OSCAL Foundation in late 2025; that tier is taken.
- A dashboard-driven compliance tool for GRC teams. That market is well-served.
- "The FedRAMP-authorized GRC tool that gets you to 20x authorization in 30 days." Paramify has this position with a real authorization behind it.
- "The Terraform-compliant-at-module-download-time registry." compliance.tf has this position.

Efterlev **is** trying to be:
- **The pure-OSS, KSI-native compliance scanner for FedRAMP 20x.** Apache-2.0 forever, no managed tier, no commercial layer. Primary abstraction is the Key Security Indicator; primary output is FRMR-compatible JSON. No other OSS tool is KSI-native today.
- The repo-native scanner that lives in the developer's codebase and runs wherever they want it to run — laptop, any CI, any cloud, GovCloud EC2, air-gapped container.
- The detect-then-remediate-with-human-review tool, complementing — not replacing — prevention-model tools like compliance.tf.
- The tool that produces code-level findings, remediation diffs posted as real PRs, FRMR-compatible validation data, and (v1.5+) OSCAL output for downstream Rev5-transition consumers.
- Deep, not broad — FedRAMP 20x + DoD IL done well rather than five frameworks at 40–60% coverage each.
- Deployable inside FedRAMP-authorized boundaries via AWS Bedrock in GovCloud (pre-launch readiness gate A3) — a path SaaS-first competitors cannot match without their own FedRAMP authorization.

---

## The detailed landscape

### Paramify — the category-defining FedRAMP 20x specialist (2026-04-23 update)

Commercial SaaS GRC automation tool, FedRAMP-specialist. Authorized through the FedRAMP 20x Phase 2 Moderate pilot and now markets "FedRAMP 20x authorization in under 30 days" with the Phase 2 submission as the backing case study ([paramify.com/fedramp-20x](https://www.paramify.com/fedramp-20x), accessed 2026-04-23). Pricing is disclosed publicly at ~$145–180K initial plus $235–360K annual ([paramify.com/blog/fedramp20x](https://www.paramify.com/blog/fedramp20x)).

**Where they overlap with Efterlev:** both target the "first-time FedRAMP 20x Moderate" SaaS user. Both produce FRMR-compatible authorization-package artifacts. Both accelerate the path from first-engagement to 3PAO-submissible package.

**Where they don't overlap:**
- Paramify is SaaS, account-bound, paid. Efterlev is pure OSS, Apache-2.0, local-first, no account.
- Paramify is GRC-shaped: policy library, evidence-collection dashboard, audit-prep workflow. Efterlev is developer-tool-shaped: CLI in the repo, PR comments, remediation diffs, CI integration.
- Paramify does not scan Terraform source for KSI evidence or produce code-level remediation diffs. Efterlev does both.
- Paramify's pricing is on the order of 1–2 engineer-years per year, which is a meaningful budget line item for the 50–200-person ICP. Efterlev is free forever.
- Paramify's "authorization in 30 days" is a packaged service with their tooling driving it; Efterlev is a tool a customer's own team drives.

**Who picks which:** a SaaS company willing to spend ~$180K to compress their first-FedRAMP timeline, with a dedicated compliance person or appetite to hire one, picks Paramify. A SaaS company that wants to own the work, keep costs near-zero, and use the same tool to maintain compliance post-authorization picks Efterlev. Different buyer, different budget authority, different time horizon.

**The risk to Efterlev:** Paramify owns the "fast FedRAMP 20x authorization" narrative with case-study backing we don't have. Our counter-narrative — "run this free tool against your repo yourself" — has to convert on first-five-minutes experience, because we don't have the budget or institutional weight to counter their sales motion head-on.

### compliance.tf — the closest technical substitute (added 2026-04-23)

Terraform compliance tool that enforces 185 FedRAMP Moderate Rev 4 controls automatically via compliant module replacements at Terraform registry download time ([compliance.tf](https://compliance.tf/), accessed 2026-04-23). Scan/edit/enforce custom rules shipping Q2 2026 ([compliance.tf/hipaa](https://compliance.tf/hipaa/)). Supports multiple frameworks (FedRAMP, SOC 2, PCI DSS, HIPAA, NIST, CIS, ISO 27001, GDPR).

**Where they overlap with Efterlev:** both operate at the Terraform layer. Both target engineers doing FedRAMP Moderate work. Both are CI-pipeline-friendly. Both emit findings tied to specific controls.

**Where they don't overlap:**
- compliance.tf is a *prevention-model* tool — non-compliant infrastructure fails at module-download time, which is simpler to pitch ("you can't deploy non-compliant infrastructure") but also requires the customer to buy into their module registry. Efterlev is a *detection-then-remediation* model — works against any existing Terraform codebase without rewriting, with LLM-drafted remediation diffs.
- compliance.tf leads with FedRAMP Rev 4 (the legacy control set). Efterlev leads with FedRAMP 20x KSIs and Rev 5 controls — the 2026+ trajectory.
- compliance.tf does not emit FRMR-compatible attestation JSON; it's a build-time enforcement tool. Efterlev produces validation artifacts consumable by 3PAOs.
- compliance.tf does not use AI agents for classification or remediation; it's a rules-engine replacement-module strategy. Efterlev uses Claude for gap classification, narrative drafting, and remediation.
- compliance.tf is commercial; Efterlev is pure OSS.

**Who picks which:** a team starting fresh on their FedRAMP-boundary Terraform picks compliance.tf and gets prevention-by-default. A team with an existing Terraform codebase that wants to understand its current state, generate evidence, draft attestations, and iteratively remediate picks Efterlev. Teams that want both models (prevention at dev-time, detection at scan-time) can run them side by side without conflict.

**The risk to Efterlev:** if compliance.tf's Q2 2026 custom-scan-rules feature lands a convincing "we also do detection" pitch, our detection wedge narrows. Our defense: evidence-quality depth (provenance chain, FRMR-compatible JSON, LLM-drafted narratives grounded in cited evidence) plus the OSS posture compliance.tf can't match without losing their commercial-registry model.

### AWS, HashiCorp, and hyperscaler first-party risk (added 2026-04-23)

AWS has published a FedRAMP 20x automation blog ([aws.amazon.com/blogs/publicsector/prepare-for-fedramp-20x-with-aws-automation-and-validation](https://aws.amazon.com/blogs/publicsector/prepare-for-fedramp-20x-with-aws-automation-and-validation/), accessed 2026-04-23). If AWS ships a first-party KSI-validation toolkit inside Bedrock / Audit Manager / Security Hub — with deep AWS-native integration that a third-party OSS tool cannot match — the "scan your AWS Terraform for KSI evidence" wedge narrows sharply for AWS-Terraform-primary customers.

HashiCorp similarly owns the Terraform layer directly and could ship a FedRAMP-specific Sentinel or policy-as-code pack that covers the same surface.

**The risk to Efterlev:** first-party tools win on ecosystem integration; they lose on cross-cloud and on "runs anywhere" claims. Our defense: multi-cloud detector footprint (pre-launch gate A4 is AWS-only; post-launch C3 adds GCP and Azure starter detectors), cloud-agnostic detector contract, and explicit "no-lock-in" positioning. AWS first-party means AWS-lock-in; our OSS posture gives customers an exit and a unified multi-cloud pipeline that first-party tools structurally can't.

### Secureframe — Phase 2 pilot participant (added 2026-04-23)

Listed previously under "commercial SaaS players, not AI-native" but upgraded to a separate mention because Secureframe was a FedRAMP 20x Phase 2 pilot participant ([secureframe.com/blog/fedramp-20x-phase-two](https://secureframe.com/blog/fedramp-20x-phase-two), accessed 2026-04-23). They can credibly claim FedRAMP 20x experience their SaaS-compliance-first competitors (Vanta, Drata) cannot. Their product remains SaaS-dashboard-shaped, so the locus-of-work difference with Efterlev holds, but their marketing authority on the 20x topic is now specific rather than general.

### Comp AI (trycompai) — adjacent OSS AI compliance platform

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

> Is there a user for whom the pure-OSS, repo-native, FedRAMP-focused, KSI-native scanner is the right tool — and who would not be well-served by Paramify, compliance.tf, Comp AI, RegScale, or Vanta?

The answer is yes, and the user is specific. Efterlev's primary ICP is a **SaaS company (50–200 engineers) pursuing its first FedRAMP Moderate authorization** — typically triggered by a federal customer deal contingent on authorization. The work is owned by a DevSecOps lead or senior platform engineer; the urgency comes from the CEO and the revenue on the line; the buyer is not yet ready to commit $180K to a GRC tool before seeing value. Full profile at [docs/icp.md](./docs/icp.md).

For this user:

- **Paramify is the wrong entry point.** Excellent tool once a company decides to spend $180K on a compliance accelerator with dedicated sales engagement, but the ICP's DevSecOps lead cannot authorize that purchase without internal evidence the investment pays off. Efterlev is the free, repo-native, zero-procurement first step that produces that internal evidence — after which, if the company wants paid workflow automation on top, Paramify is the natural upgrade path.
- **compliance.tf is the wrong model (at first).** Their prevention-at-module-download-time strategy is elegant for teams starting fresh, but the ICP usually has an existing Terraform codebase they need to understand and remediate rather than rewrite against a new registry. Efterlev works against their current code. Detection complements prevention; teams running both cover more surface than either alone.
- **Comp AI is the wrong depth and the wrong era.** Their FedRAMP coverage (41% in their own demo) reflects their broader SOC 2–first positioning and maps to legacy Rev5 controls. An ICP A user starting FedRAMP in 2026 is heading into 20x, where the KSIs are what matter. Efterlev is KSI-native; Comp AI is not.
- **RegScale is the wrong tier.** Built for Authorizing Officials, ISSOs, and mature compliance organizations, with deep OSCAL infrastructure. An ICP A SaaS company doesn't have that team yet, and is better served by FRMR than by OSCAL for 20x work.
- **Vanta/Drata are the wrong shape.** SaaS dashboards optimized for SOC 2 / ISO 27001; their FedRAMP modules are thinner and their locus is wrong for a single-engineer DevSecOps lead.

Secondary ICPs (defense contractors pursuing CMMC 2.0 / DoD IL; platform teams at larger gov-contractor orgs) are named in `docs/icp.md` as v1.5+ and v2+ expansions. They are well-served by the architecture we're building but are not the v0 focus.

For a SaaS compliance team doing SOC 2 + HIPAA, Comp AI is the right tool. For a company that wants a packaged authorization-in-30-days service with tooling included, Paramify is the right tool. For teams starting fresh on compliant infrastructure at module-download time, compliance.tf is the right tool. For an Authorizing Official reviewing packages, OSCAL Hub is the right tool. These markets overlap at the edges but have distinct centers of gravity, and this is healthy.

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
