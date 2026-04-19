# Ideal Customer Profile

This document names the user Efterlev is designed for. It is the lens for every product decision. When we ask "should we add X?", the test is: does X serve the primary ICP's workflow? If not, X is deferred or declined — however technically interesting it may be.

This document is not a marketing persona. It is an engineering constraint.

---

## The primary ICP (v0 and v1)

**A SaaS company pursuing its first FedRAMP Moderate authorization.**

### Who they are

- **Company stage:** 50–200 engineers. Strong commercial product-market fit. Profitable or venture-funded with real revenue.
- **Product:** A B2B SaaS offering — horizontal (observability, data, CRM, collaboration) or vertical (healthcare, fintech, GRC, security). The product already works and has commercial customers.
- **Trigger event:** A federal agency or a federal prime contractor has indicated they will buy the product *if* it achieves FedRAMP Moderate authorization. Revenue is on the line — typically a committed deal in the $500K–$5M range, or a pipeline of several such deals.
- **Who feels the pain first:** The VP of Engineering, the CTO, or the Head of Security. They are the ones the CEO turns to with "we need FedRAMP — how long?" They don't have the answer.
- **Who does the work:** A DevSecOps lead or senior platform engineer, often the same person who owns the CI pipeline and the Terraform. They're the one who will `pipx install efterlev` at 11pm on a Tuesday.

### What they don't have

- **A compliance team.** At this scale, "compliance" is a hat worn part-time by the Head of Security or outsourced to consultants.
- **Prior FedRAMP experience.** This is their first time. They don't know what an SSP looks like in the wild. They've heard of OSCAL but don't use it.
- **Budget for enterprise compliance platforms.** RegScale and Xacta are priced for larger buyers. Vanta and Drata are affordable but weak on FedRAMP depth (Comp AI shows 41% FedRAMP coverage in their own demo for a reason — it's not their primary target).
- **Time.** The commercial deal has a deadline. 18 months feels impossibly long; six is aspirational; 12 is survivable.

### What their situation looks like concretely

They have:

- **Some infrastructure-as-code, often mixed.** Terraform is the most common, but many ICP A users have CloudFormation, AWS CDK, Pulumi, or a mix — and almost all have Kubernetes manifests for their workloads. A subset have ClickOps-provisioned resources nobody remembers creating. Their IaC maturity is typically the pre-FedRAMP state of things, and the FedRAMP effort is often what forces the codification.
- **A fresh or nearly-fresh FedRAMP boundary (common pattern).** Many ICP A companies run their FedRAMP deployment as a parallel dedicated environment (often a separate AWS account, often in GovCloud) rather than inside their main commercial production. This means the Terraform scanned for the authorization is frequently newer and cleaner than the rest of their codebase, which is useful for v0's Terraform-only coverage.
- **A modern engineering stack.** GitHub, CI via GitHub Actions or CircleCI, containerized workloads (ECS, EKS, Lambda).
- **An existing security posture appropriate for a commercial SaaS** — good enough for SOC 2 Type II or ISO 27001, not obviously ready for FedRAMP Moderate.
- **A consultant engagement (or a pending one)** with a FedRAMP advisor at $200–$500/hour. This consultant may also have recommended a 3PAO.

They need to produce:

- A gap analysis against FedRAMP Moderate Rev 5 (~323 controls + enhancements)
- An SSP that passes initial 3PAO review
- A POA&M for known gaps
- Evidence packages for each implemented control
- And — increasingly, given RFC-0024's September 2026 mandate — all of the above in machine-readable OSCAL format

### Implications for what Efterlev accepts as input

v0 scans **Terraform and OpenTofu** (shared syntax; `python-hcl2` handles both). This covers the largest single slice of ICP A's infrastructure and maps naturally to the "fresh FedRAMP boundary" pattern above.

v0 explicitly does **not** cover: CloudFormation, AWS CDK, Pulumi, Kubernetes manifests, or runtime cloud API scanning. These are v1 priorities in the following order of impact for ICP A:

1. **Terraform Plan JSON** — scanning resolved plans rather than raw HCL catches computed values. High value, low cost. v1 early.
2. **CloudFormation / CDK** — CDK compiles to CloudFormation, so one parser covers both. Many AWS-native ICP A users have some of this. v1 month 1–2.
3. **Kubernetes manifests + Helm** — different control set (network policies, pod security, RBAC) but nearly universal in ICP A production. v1 month 2–3.
4. **Pulumi** — code-first IaC; trickier parsing but real demand. v1 month 3–4.
5. **Runtime cloud API scanning** — the "real" answer for partially-codified infrastructure. Different threat model, needs its own design pass. v1.5+.

The architectural commitment that makes this expansion cheap: the detector contract is already source-typed (`source="terraform"` is a field on the decorator), and the detector library folder structure has room for parallel `detectors/aws/cloudformation/`, `detectors/k8s/`, etc. Adding a source type is adding a parser and a set of parallel detectors — not a rearchitecture.

**An ICP A user with a mixed-IaC codebase** should see this explicitly in our positioning. If 60% of their infrastructure is Terraform, v0 covers the majority and they get real value. If they're 100% CloudFormation, v0 is not for them yet and we should be honest about that.

### What their day-one Efterlev experience needs to be

1. They hear about Efterlev from a blog post, a Hacker News thread, a recommendation in a DevSecOps Slack, or a FedRAMP consultant who tried it.
2. They clone the demo or point Efterlev at their own repo. `pipx install efterlev` takes 90 seconds.
3. `efterlev scan` produces findings within 30 seconds. The findings are concrete: "S3 bucket `production-data` lacks server_side_encryption_configuration at `main.tf:142`."
4. `efterlev agent gap` classifies their posture across the six (v0) controls with confidence and evidence. They see, for the first time, a machine-generated sketch of where they stand.
5. `efterlev agent document --control SC-28` produces an OSCAL-aligned draft SSP narrative for one control, citing their actual Terraform lines. They forward this to their FedRAMP consultant, who says "this is 70% of what I'd write myself."
6. Within their first session, they have: a concrete gap list, a draft SSP section, a remediation diff for at least one finding, and a clear sense that *more detectors would produce more of the same*.
7. Within week one, they have added Efterlev to their CI pipeline. PRs now carry a compliance delta. The tool is now part of their workflow, not an occasional scan.

### What makes them keep using Efterlev after week one

- Every new detector we ship extends their coverage without any work on their part. Breadth compounds.
- The OSCAL output works with their 3PAO's tooling. They don't have to explain or translate.
- The provenance chain makes the tool defensible in 3PAO conversations: "here's where each claim in our draft came from."
- CI integration catches regressions before they become audit findings.
- The Remediation Agent produces diffs their team can review and apply, shrinking the time from finding to fix.

### What we must not do to ICP A

- Force them into a SaaS dashboard. They live in the repo.
- Require cloud API access. Many ICP A users don't want a tool with IAM read access to their production account; Terraform source is the right abstraction.
- Overclaim. If Efterlev's output says "SC-28 is implemented" when we've only evidenced the infrastructure layer, their 3PAO will catch the overclaim and we will lose their trust permanently.
- Add features that serve compliance teams instead of engineers. ICP A *does not have* a dedicated compliance team; features designed for one are dead weight.

---

## Secondary ICPs (v1+ expansion)

Named explicitly so we know where we're going without diluting current focus.

### ICP B — The defense contractor pursuing CMMC 2.0 Level 2 or DoD IL

- **Company stage:** 200–1000+ engineers at a defense-industrial-base company.
- **Trigger event:** CMMC 2.0 enforcement is now real; loss of DoD contracts if not certified by the deadline.
- **Why they're secondary for v0:** We don't ship CMMC coverage until v1 (month 5 of the roadmap). Serving them well requires AWS Bedrock in GovCloud (v1), CUI-aware data handling, and air-gap-ready operation.
- **When they become primary:** v1.5–v2, once CMMC overlay, Bedrock backend, and segregation-aware workflows exist.
- **What the expansion requires:** Bedrock backend (committed v1), CMMC 2.0 profile and mappings, IL-overlay detectors, secrets handling hardening beyond v0.

### ICP C — The DevSecOps platform team at a larger gov-contracting org

- **Company stage:** 1000+ engineers. Mature platform team. Already has in-house compliance tooling or a partial SaaS deployment.
- **Trigger event:** They are building or consolidating an internal compliance pipeline for many downstream teams.
- **Why they're secondary for v0:** They need features we haven't built — organization-specific detector contribution workflow, multi-repo coordination, role separation between platform and consumer teams, integration with their existing observability and GRC stack.
- **When they become primary:** v2+, once we have a healthy external contributor ecosystem and proven composability.
- **What the expansion requires:** Mature plugin architecture for detectors (committed), multi-repo state handling, integration with RegScale / OSCAL Hub / Xacta for downstream consumption, organization-scoped policy packs.

---

## Who we are not trying to serve

Explicitly named to avoid drift.

- **Companies pursuing SOC 2 only.** Comp AI, Vanta, Drata, Secureframe, and a dozen others serve this market well. Efterlev's gov-grade depth is wasted here.
- **Companies pursuing ISO 27001, HIPAA, PCI-DSS, or GDPR as their primary framework.** Efterlev can produce supporting evidence for these, but we are not building detector libraries for them. Other tools are better fits.
- **Compliance teams at enterprises already using RegScale, Xacta, or Ignyte.** These tools serve the GRC/AO/ISSO workflow; Efterlev is a developer-side complement, not a replacement.
- **Authorizing Officials, 3PAOs, and FedRAMP PMO reviewers.** Efterlev produces artifacts they consume; OSCAL Hub and similar platforms are purpose-built for their review workflow.
- **Companies that want a compliance dashboard.** Our locus is the repo and the CLI. Users who want a dashboard are not served well by us.
- **Companies that want to "vibe-code" compliance.** Efterlev refuses to claim authorization, refuses to generate narrative without evidence, and flags every LLM-generated artifact as requiring human review. Teams that want plausible-looking output without rigor will be disappointed, which is the correct outcome.

---

## How this document drives decisions

A non-exhaustive list of product decisions this ICP answers:

- **"Should we add a web UI?"** → Not for ICP A. Defer.
- **"Should we support SOC 2?"** → Not for ICP A. Defer indefinitely.
- **"Should we build continuous monitoring?"** → Roadmap month 6. ICP A gets value from point-in-time scans + CI integration; continuous monitoring is more valuable to ICP B and C.
- **"Should we add a multi-tenant SaaS mode?"** → No. ICP A runs locally. ICP B often cannot use multi-tenant SaaS at all.
- **"Should the Gap Agent's output be auto-submitted to a 3PAO portal?"** → No. ICP A uses human-in-the-loop; their consultant and 3PAO are part of the workflow.
- **"Should we add a 'quick check' mode with fewer controls for faster scans?"** → Worth considering for ICP A — they want fast feedback in CI. Potential v1 feature.
- **"Should we support Pulumi / CloudFormation / Kubernetes manifests?"** → ICP A is mostly Terraform-first. Pulumi and Kubernetes manifests are v1 priorities; CloudFormation is v1.5 unless a specific ICP A user needs it.
- **"Should we integrate with Jira?"** → Likely yes in v1. ICP A's workflow involves tracking findings as tickets.

---

## Validating the ICP choice

This document is a hypothesis. It will be tested by actual usage. Signals that ICP A is right:

- First 10 non-author GitHub stars come from engineers at SaaS companies in the 50–200 range.
- First external contributor PR addresses a control ICP A would hit in a real FedRAMP engagement.
- First "this worked for us" issue or blog post comes from a company matching the ICP A profile.

Signals we may be wrong:

- Early interest is dominated by ICP C (platform teams) — would suggest we lead with composability and plugin docs sooner.
- Early interest is dominated by consultants rather than end users — would suggest the buyer is different from the ICP we modeled.
- Early interest is dominated by ICP B (defense contractors) — would accelerate the CMMC and Bedrock roadmap.

We re-evaluate this document at v0.2 (post-hackathon, first external usage) and at every minor release thereafter. Updates are logged in `DECISIONS.md`.

---

*Last reviewed: initial draft. Update this date with every review.*
