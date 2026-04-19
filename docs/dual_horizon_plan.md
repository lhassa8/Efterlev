# Efterlev: Dual-Horizon Build Plan

**Project:** Efterlev — a repo-native, agent-first compliance scanner for FedRAMP and DoD Impact Levels; OSCAL as a first-class output format
**Builder:** solo + Claude Code (Opus 4.7) for hackathon; growing contributor base thereafter
**License:** Apache 2.0
**Governance:** BDFL-style during v0–v1; explicit invitation to co-maintainers at 10 active contributors
**Commercial posture:** Pure OSS. Paid support and enterprise-specific features possible later; core library remains Apache 2.0 forever.

This plan covers two horizons on a shared architecture:

- **Layer 1 — Hackathon MVP (4 days):** Tight vertical slice; demo-optimized; proves the architecture.
- **Layer 2 — Post-hackathon v1 (3–6 months):** Expansion along named axes; adoption-optimized; becomes the default OSS tool for gov-adjacent compliance automation.
- **Layer 3 — The long bet (6–18 months):** If traction materializes, becomes the open reference implementation for FedRAMP 20x's machine-readable vision.

The discipline binding the layers: **nothing built in Layer 1 is thrown away to build Layer 2.** Every architectural choice at the hackathon stage must serve the v1 target.

---

## 1. Shared architectural commitments

These hold across both horizons. They are the load-bearing decisions.

### 1.1 The detection library is a first-class concept

Not a folder of scanners inside `primitives/`. A self-contained, contribution-friendly library where each control detector is an independent artifact with a defined shape: rule logic, control mapping, evidence template, test fixtures. A contributor can add a new detector without touching the rest of the codebase.

```
detectors/
├── aws/
│   ├── sc_28_s3_encryption/
│   │   ├── detector.py         # the rule logic
│   │   ├── mapping.yaml        # control mapping(s), including enhancements
│   │   ├── evidence.yaml       # evidence template (our internal schema, not OSCAL)
│   │   ├── fixtures/           # IaC samples that should match / should not
│   │   └── README.md           # human-readable explanation
│   └── ...
├── k8s/                        # v1 expansion
├── github_actions/             # v1 expansion (for CI-based controls)
└── universal/                  # controls that span sources
```

This structure ships in the hackathon build with six detectors. In v1, it grows via community PRs. In v2, it becomes the moat.

### 1.2 Primitive/detector/agent separation

Three distinct concepts with different contracts:

- **Detectors:** Rule-like artifacts that read source material and emit evidence candidates. Narrow, deterministic, independently testable. The community contributes these.
- **Primitives:** Typed Python functions exposed via MCP that represent agent-legible capabilities — scan an artifact using the detector library, map a control, resolve a profile, generate a narrative, validate OSCAL. ~15–25 in total. Stable surface area.
- **Agents:** Reasoning loops that compose primitives to accomplish a goal. Small number — Gap, Documentation, Remediation for v0; Drift, Auditor, Mapper for v1.

Detectors feed primitives. Primitives feed agents. Agents produce artifacts. Everything is provenance-tracked.

### 1.3 OSCAL as a first-class output format, not the core internal model

The core internal data model is our own — a set of domain-shaped Pydantic types for Controls, Evidence, Findings, Claims, Mappings, and Provenance that are designed around the tool's actual job. OSCAL is not the internal representation. This is a deliberate reversal of the earlier position.

The reasoning:

- The compliance knowledge that matters — which controls mean what, which IaC patterns evidence which controls, how frameworks map — lives in our detector library and our mapping library. OSCAL is a way of *expressing* that knowledge to other systems; it is not where the knowledge lives.
- OSCAL's SSP model is complex and opinionated in ways that don't help the core value. Forcing the internal model through OSCAL types adds engineering overhead that doesn't improve detection quality, narrative quality, or agent reasoning.
- OSCAL adoption at 3PAOs and agencies today is thinner than the pitch implies. Most still consume FedRAMP Word/Excel templates. The machine-readable future is real but gradual (3–5 year transition). Building OSCAL-native *internally* today bets too hard on a pace that isn't here yet.
- Users don't ask for OSCAL. They ask for findings, drafts, and reports. OSCAL matters to the downstream compliance team and to government systems, and it matters only at the output boundary.

What this looks like in practice:

- **Internal model:** Owned Pydantic types, simple, fast to iterate on. Agents reason over these types, not over OSCAL types.
- **Input side:** `compliance-trestle` used to load OSCAL catalogs and profiles published by NIST and FedRAMP, immediately translated into our internal model. We don't keep OSCAL objects in memory as our working representation.
- **Output side:** OSCAL generators are dedicated primitives that serialize our internal model to OSCAL artifacts (Assessment Results, partial SSP, POA&M). Alongside other generators as we add them — FedRAMP Word template, HTML report, markdown summary, GRC-tool JSON.
- **Validation:** OSCAL output is validated against the schema before return. An invalid OSCAL artifact is never returned.

OSCAL stays a first-class *commitment* — we produce standards-compliant output, we ship with OSCAL generators from day one, and the tool is legitimately useful to anyone consuming OSCAL. It just isn't the language the rest of the system speaks to itself.

### 1.4 Provenance as a queryable graph, not a log

Every claim (evidence, finding, narrative, mapping, remediation) is a node in a directed graph. Edges point from derived claims to their upstream sources. The graph is content-addressed (SHA-256 of canonical content), timestamped, and versioned — evidence records are *appended*, never overwritten.

This design serves both horizons:
- **v0:** Enables the "walk the chain from this SSP sentence back to the Terraform line" demo moment.
- **v1:** Enables "show me every control whose evidence has changed in the last 30 days" — the continuous monitoring story.

Storage: SQLite for the graph structure and metadata, content-addressed blob store on disk for claim content. Simple, portable, air-gap-friendly.

### 1.5 Evidence versus claims: a hard distinction

Two classes of information, treated differently throughout the system:

- **Evidence** is deterministic, scanner-derived, and high-trust. Produced by detectors. Every piece of evidence carries a raw source reference (file + line + hash).
- **Claims** are reasoned output — LLM-generated narratives, mappings, rankings, remediation proposals. Every claim carries a confidence indicator and an explicit "requires human review" flag.

The distinction is visible in the data model, the UI (when it exists), the OSCAL output, and the provenance store. This is the defensible answer to "how does a 3PAO trust this?" The answer is: they don't trust the claims, they trust the evidence — and the claims are drafts that accelerate the human workflow.

### 1.6 Pluggable LLM backend

The agent base class abstracts model calls cleanly enough that swapping backends is config, not code. Default: Claude Opus 4.7. For v1, users can configure local models via Ollama or equivalent for air-gapped environments. We don't *support* non-Claude backends in v0 — we just don't foreclose them.

### 1.7 Extension via Python entry points

Contributors can publish `efterlev_detector_*` and `efterlev_agent_*` packages that register themselves via Python entry points. The core package has no registry to maintain; the ecosystem grows through standard Python packaging. Skeleton in place for v0, documented and tested in v1.

### 1.8 Local-first; CI-ready in v1

**v0 / v1.0:** Local CLI tool. Zero telemetry. Zero phone-home. Content-addressed store is local only. This is a security posture; it's also the adoption wedge — no procurement cycle for a `pipx install`.

**v1.x:** CI integration as a first-class mode. `efterlev scan` runs in GitHub Actions / GitLab CI on every PR; findings get posted as PR comments; provenance store persists in a designated artifact bucket. This is where the DevSecOps pitch becomes real.

**v2 consideration:** Runtime agent scanning live infrastructure. Not committed. Architecturally, the detector interface is the same; the input source changes from "Terraform plan" to "cloud API response."

### 1.9 Threat model for the tool itself

A compliance tool that reads IaC encounters secrets, private topologies, sensitive architecture. From day zero:

- No network calls except to the configured LLM endpoint
- No telemetry, analytics, or error reporting
- Secrets detected during scanning are hashed before entering the provenance store, never logged in plaintext
- The provenance store is world-readable by default only within the local user's home directory
- A `THREAT_MODEL.md` ships in the repo, names these commitments, and invites review

### 1.10 Honesty commitments (product-level guardrails)

Enforced in the code and the docs:

- The tool never claims to produce an authorization, a pass, or a guarantee of compliance. It produces drafts and findings.
- Every LLM-generated narrative carries an explicit "DRAFT — requires human review" marker in OSCAL metadata and in rendered output.
- Confidence levels on generated mappings and narratives are visible, not buried.
- `LIMITATIONS.md` is a first-class document and is updated alongside feature work, not at release time.

---

## 1a. Competitive landscape and positioning

The market moved fast during planning. As of April 2026, the relevant landscape:

**Closest overlapping player — Comp AI (trycompai).** Open-source, AI-agent-driven, covers SOC 2 + ISO 27001 + HIPAA + GDPR + FedRAMP across one SaaS-first platform. 600+ customers. Their model: continuous evidence collection from 500+ SaaS integrations, AI-generated policies, OSS device agent, cloud monitoring. Their FedRAMP coverage score in their own demo is ~41% — they cover it as one framework among many, not as a focus. They do not scan Terraform source code. They do not run as a CLI in the developer's repo. They do not produce code-level remediation diffs.

**OSS OSCAL platform tier — RegScale OSCAL Hub.** Donated to the OSCAL Foundation in late 2025. Positioned as "the industry's first comprehensive, open-source platform purpose-built for working with OSCAL documents." Document-processing and review-workflow tooling for Authorizing Officials, the FedRAMP PMO, and ISSOs. This tier is taken. We are not competing with it — we are a potential *producer* of OSCAL that Hub consumers can review.

**Adjacent OSS, dormant or narrow:** StrongDM Comply (SOC 2-focused policy site generator, largely dormant), 18F compliance-toolkit (OpenControl Masonry era, inactive), GoComply/fedramp (OSCAL-to-Word converter, narrow scope), mrice/complykit (2013-era license-check Maven plugin, dormant).

**What this means for our positioning:**

- We are **not** "the open-source AI compliance platform." That space has a player with real traction.
- We are **not** "the OSS OSCAL platform." That position was taken in late 2025.
- We **are** the **repo-native, agent-first, FedRAMP-and-DoD-IL-focused scanner** that lives in the developer's codebase and CI pipeline, scans IaC and application source at PR-time, produces code-level findings and remediation diffs, and emits standards-compliant OSCAL for downstream consumption by tools like OSCAL Hub.

The distinctions that matter:

- **Where we live.** SaaS compliance platforms live in a dashboard the compliance team opens. Efterlev lives in the repo the engineer is already in. Different locus, different UX, different buyer.
- **Who we serve first.** The primary ICP is a SaaS company (50–200 engineers) pursuing its first FedRAMP Moderate authorization, with a committed federal deal on the line. Work is owned by a DevSecOps lead or senior platform engineer. Not the GRC team (they don't have one yet); not the Authorizing Official (downstream consumer); not the defense contractor doing CMMC (v1.5+). Full profile at `docs/icp.md`.
- **Depth, not breadth.** FedRAMP Moderate + FedRAMP High + DoD IL2/4/5/6 done well beats five frameworks at 40-60% each. IL is a market Comp AI does not serve and where the government-contractor pain is most acute.
- **Claude Code and MCP as architecture, not marketing.** No competitor in our scan is built around MCP as the extension surface. The meta-loop (Claude Code builds Efterlev, Efterlev uses Claude for reasoning, external Claude Code drives Efterlev via MCP) is a unique demo and a unique architectural commitment.
- **Evidence-vs-claims discipline.** No surveyed tool has the explicit architectural distinction between deterministic scanner-derived evidence and LLM-reasoned claims. This is the defensible answer to 3PAO scrutiny that nobody else is giving.

What we retire from the pitch:
- Any framing that positions incumbents as "dashboards with workflow automation" without acknowledging Comp AI. That was the 2024 landscape.
- "OSS OSCAL-native platform" language. Use "emits standards-compliant OSCAL output" instead.
- Market-size claims that conflate gov-software-TAM with compliance-tooling-TAM.

What we keep:
- The thesis that compliance is an agentic workload.
- The regulatory tailwinds (FedRAMP 20x, OMB M-24-15, RFC-0024's September 2026 OSCAL deadline, CMMC 2.0).
- The open-source commitment.
- The dev-tool-shaped positioning that nobody else is occupying.

This section ships in the repo as `COMPETITIVE_LANDSCAPE.md` — first-class, not hidden. Judges and contributors both respect honest positioning.

---

## 2. Hackathon MVP (Layer 1) — the 4-day build

The discipline: **one vertical slice first, then replicate.** Day 1 produces a working end-to-end path for one control. Days 2–4 replicate for five more, add agents, add polish.

### 2.1 Scope

**Six controls, chosen for clean IaC-detectability:**

| Control | Name | Detection signal |
|---|---|---|
| SC-28 | Protection of Information at Rest | S3/RDS/EBS encryption settings |
| SC-8  | Transmission Confidentiality      | TLS configuration, ALB listener protocol |
| SC-13 | Cryptographic Protection          | Algorithms in use; FIPS mode |
| IA-2  | Identification & Authentication   | MFA enforcement on IAM |
| AU-2 + AU-12 | Event Logging & Audit Generation | CloudTrail scope |
| CP-9  | System Backup                     | RDS automated backups; S3 versioning |

**Three agents, each with a distinct reasoning task:**

- **Gap Agent:** Classifies each control as `implemented` / `partially implemented` / `not implemented` / `compensating control` / `not applicable`, given evidence. Reasoning task: distinguishing partial from full implementation from compensating controls requires nuance a deterministic function can't handle.
- **Documentation Agent:** Drafts SSP narrative for each implemented or partially-implemented control, with every sentence carrying an evidence-ID citation. Output is OSCAL-aligned implemented-requirements.
- **Remediation Agent:** Given a single finding (e.g., unencrypted S3 bucket), proposes a concrete code change as a diff. The Claude Code hero moment.

**One cloud, one IaC tool:** AWS + Terraform. Nothing else. Azure, GCP, Pulumi, CloudFormation, Kubernetes manifests all deferred.

### 2.2 Demo repo (`demo/govnotes`)

Pre-built before day 1. A fictional gov-adjacent SaaS with:

- Terraform for AWS: VPC, RDS (encrypted), S3 (some encrypted, some not — deliberate gap), ALB with TLS 1.2+ on one listener and TLS 1.0 allowed on another (deliberate gap), CloudTrail in one region only (deliberate gap), IAM roles (some with MFA enforcement, some without — deliberate gap), Secrets Manager for credentials, automated RDS backups
- A Node or Python API with auth middleware and structured logging
- README framed as a real company's public posture

The deliberate gaps are what the Gap Agent flags and the Remediation Agent fixes in the demo.

### 2.3 Day-by-day

**Day 0 (pre-hackathon):**
- Demo repo built and pushed
- `CLAUDE.md`, `DECISIONS.md`, `LIMITATIONS.md`, `THREAT_MODEL.md`, `CONTRIBUTING.md` drafted
- FedRAMP Moderate OSCAL baseline downloaded to `catalogs/`
- License committed, GitHub org named, repo skeleton pushed
- MkDocs Material set up for docs (empty shell is fine)

**Day 1 — one vertical slice, SC-28 only, on our own model:**
- Internal Pydantic models: Control, Evidence, Finding, Claim, Mapping, ProvenanceRecord. Clean, small, owned.
- Detector library structure in place; one detector (`detectors/aws/sc_28_s3_encryption/`) complete with fixtures
- One scan primitive (`scan_terraform`) that loads detectors and runs them
- Provenance store writing and reading claims against the internal model
- Content-addressed blob store working
- CLI: `efterlev init` and `efterlev scan`
- **End-of-day demo:** `efterlev scan ./demo/govnotes` produces findings for SC-28 with provenance hashes walkable back to source. One control, working end-to-end, on the internal model.

**Day 2 — replicate detectors; OSCAL loading; MCP; Gap Agent:**
- Five more detectors (SC-8, SC-13, IA-2, AU-2+AU-12, CP-9) using the pattern from day 1
- OSCAL loader: trestle-based, translates FedRAMP Moderate OSCAL baseline into our internal Control + Profile model. One-way for now; we load OSCAL, we don't round-trip.
- MCP server exposing the primitive set
- External Claude Code connection tested
- Gap Agent built, invokable via CLI, producing internal GapReport objects
- HTML report generator for the gap report (Jinja template)
- **End-of-day demo:** `efterlev agent gap` produces a readable report across all six controls, with provenance. FedRAMP Moderate baseline loaded from official OSCAL.

**Day 3 — Documentation Agent; Remediation Agent; OSCAL output generators:**
- Documentation Agent producing internal SSPDraft objects with evidence citations in every sentence
- OSCAL SSP generator: serializes internal SSPDraft to a partial OSCAL SSP (implemented-requirements section). If trestle's SSP generation is clean, use it; if not, hand-roll the serialization. Decision logged in `DECISIONS.md`.
- `validate_oscal` primitive, passing validation on generated output
- HTML SSP generator alongside OSCAL — demo-friendly, human-readable
- Remediation Agent working for SC-28 specifically — produces a diff fixing the unencrypted bucket
- **End-of-day demo:** full end-to-end flow. SSP draft generated in both OSCAL and HTML, with citations. Remediation diff shown.

**Day 4 — polish, docs, demo recording:**
- README written for new users (not investors)
- `docs/primitives.md` auto-generated
- Quickstart tested end-to-end from `pipx install`
- Demo video recorded mid-afternoon (NOT end of day), with retake buffer
- Submission

### 2.4 Risks and mitigations

**Risk:** Trestle's SSP generation produces artifacts that fail FedRAMP's stricter validation.
**Mitigation:** Fall back to hand-rolled Pydantic for SSP serialization. Pre-decide at end of day 2 so day 3 isn't lost debugging.

**Risk:** MCP stdio transport flakes during live demo.
**Mitigation:** Pre-record the external-Claude-Code-connects-to-Efterlev moment as a fallback clip. Use it if live fails.

**Risk:** Remediation Agent produces plausible-looking but broken diffs.
**Mitigation:** Scope the demo to SC-28 specifically. Test the remediation path on day 3. If it's flaky, cut from demo video and keep in the codebase as a "coming soon" feature.

**Risk:** Scope creep during build — temptation to add the seventh control.
**Mitigation:** CLAUDE.md states the six-control limit explicitly. New controls require a scope-change decision logged in `DECISIONS.md`.

### 2.5 Demo video structure (5–7 minutes)

1. **0:00–0:45 — Problem framing.** "Government compliance takes 18 months. Let me show you what agent-first compliance looks like."
2. **0:45–1:45 — The meta-loop.** "I built this with Claude Code. It uses Claude for reasoning. And external Claude Code sessions can drive it via MCP. Three layers of the same capability." Show a brief slide + opening clip.
3. **1:45–2:45 — Live run.** `efterlev scan` streaming findings. Click into one, walk the provenance chain to the Terraform line.
4. **2:45–3:45 — Gap report.** `efterlev agent gap`. HTML report. Highlight the evidence-vs-claims distinction.
5. **3:45–4:45 — SSP draft.** `efterlev agent document`. Show narrative with citations. Note the "DRAFT — requires human review" marker. Brief glimpse of the OSCAL output alongside.
6. **4:45–5:30 — Remediation.** `efterlev agent remediate --control SC-28`. Show the PR diff.
7. **5:30–6:15 — External Claude Code.** Separate window, Claude Code connects to Efterlev's MCP server, calls a primitive. *The architectural proof.*
8. **6:15–7:00 — The arc.** "This is week one. Here's where it goes." Brief post-hackathon roadmap slide. Thank you.

---

## 3. Post-hackathon v1 (Layer 2) — the 3–6 month build

This is where Efterlev stops being a hackathon demo and becomes a useful tool that people depend on.

### 3.1 The coverage roadmap

Expansion happens along two axes in parallel: **input sources** (what Efterlev can scan) and **control coverage** (what it can find). Source-type expansion matters more for adoption — it's what moves an ICP A user from "this isn't for me yet" to "this is for me now." Control-count expansion matters more for depth and trust. Both grow in parallel; neither takes a back seat.

Public milestone targets, tracked in GitHub:

- **Month 1:**
  - Full audit of v0 code; refactor hackathon shortcuts
  - Control coverage stays at 6, but quality per detector improves
  - OSCAL SSP output passes FedRAMP validator
  - **Source expansion:** Terraform Plan JSON support (scans resolved plans including computed values, higher-fidelity than raw HCL); OpenTofu declared first-class alongside Terraform
- **Month 2:**
  - **+15 detectors** for Terraform/OpenTofu (total 21): AC-3, AC-6, CM-2, CM-6, SI-2, SI-4, SC-7, IA-5, plus additional technical controls. "Proves / does not prove" documentation for each.
  - **Source expansion:** CloudFormation and AWS CDK support (CDK compiles to CloudFormation; one parser covers both). First round of detectors ported to the new source type.
  - AWS Bedrock as a second LLM backend for FedRAMP-authorized deployments (GovCloud)
- **Month 3:**
  - **+15 detectors** (total 36)
  - **Source expansion:** Kubernetes manifests + Helm charts. New control family (network policies, pod security standards, RBAC — high value, different from cloud-resource controls).
  - Community contribution goal: first external detector PR merged
  - Tutorial on "write your own detector" published
- **Month 4:**
  - CI integration as a first-class mode. GitHub Action published. Findings-as-PR-comments working.
  - **Source expansion:** Pulumi (code-first IaC; trickier parsing, lower priority than Terraform/CloudFormation/K8s but real user demand)
- **Month 5:**
  - CMMC 2.0 overlay. Same 800-171 base as FedRAMP; CMMC-specific profile loaded and detections mapped. Second framework shipped.
  - Control coverage targeting ~60% of FedRAMP Moderate across supported source types
- **Month 6:**
  - Drift Agent: watches a repo over time, flags when a change breaks a previously-attested control. Continuous monitoring delivered in a developer-facing shape.
  - Control coverage targeting 80% of FedRAMP Moderate

**v1.5 and beyond:** Runtime cloud API scanning (different threat model, needs its own design pass); ICP B becomes primary (defense contractors on CMMC 2.0 / DoD IL) with CUI handling and air-gap mode.

### 3.2 v1 agent roster

- **Drift Agent:** Monitors the provenance graph over time. Flags when evidence for a previously-implemented control has changed or disappeared. Emits a POA&M candidate.
- **Auditor Agent (adversarial):** Red-teams the system's own conclusions. Given a Gap Agent output, tries to find the holes — evidence that shouldn't count, narratives that overreach, mappings that are stretches. Output is a critique report.
- **Mapping Agent:** Given two profiles (e.g., FedRAMP Moderate and CMMC Level 2), produces a mapping with confidence levels. Uses the 800-53 / 800-171 control graph as ground truth. Human-reviewable; a mapping accepted by a human becomes part of the shared knowledge base.

### 3.3 The knowledge base as accumulating moat

Every component contributes to a growing shared asset:

- **Detection library:** Community-contributed control detectors, each with fixtures and tests.
- **Mapping library:** Human-reviewed control mappings across frameworks.
- **Narrative library:** De-identified, reviewed SSP narrative templates contributed by users who want to give back.
- **Pattern library:** IaC anti-patterns and their compliance implications.

These live in the repo (or a companion repo) under a permissive license. Over 12–18 months, this asset is worth more than the code.

### 3.4 CI-mode architecture

`efterlev ci-scan` designed to run in a CI job:

- Reads IaC from the PR
- Runs detectors
- Compares findings to baseline (last merged main)
- Posts PR comment summarizing changes to compliance posture
- Uploads provenance deltas to artifact storage
- Exits with configured failure threshold

GitHub Action published as `efterlev/action`. Docs for GitLab CI, CircleCI equivalents. This is the shape that fits into existing dev workflows and drives adoption.

### 3.5 Community infrastructure

In place by month 2:

- GitHub Discussions for design conversations
- Discord or Slack for real-time contributor coordination
- Monthly "office hours" for contributors and users
- Clear governance doc: "I'm BDFL until 10 active contributors; then a technical steering committee forms; criteria for committee membership documented."
- Published roadmap with issues labeled "good first issue" and "help wanted"
- Security disclosure policy

### 3.6 Documentation as product

By month 3:

- Quickstart: install to first finding in 5 minutes
- Conceptual guide: "OSCAL for engineers" — explains the data model to non-compliance folks
- Tutorial: "Add your first control detector"
- Tutorial: "Integrate Efterlev into your CI pipeline"
- Tutorial: "Write a custom agent on top of Efterlev primitives"
- API reference: auto-generated from primitive decorators
- Architecture decision records (the `DECISIONS.md` promoted to versioned ADRs)

### 3.7 Honesty maintenance

- `LIMITATIONS.md` updated with every release
- A "compliance coverage reality" page honestly documenting what each control detector does and doesn't prove
- Quarterly posts or changelogs explaining what changed and why
- No marketing copy in the repo. Marketing, when it exists, lives on a separate site and is cross-linked

---

## 4. The long bet (Layer 3) — 6–18 months

If traction materializes — meaningful external contributor base, production users at gov-contracting companies, citations in FedRAMP 20x working group discussions — the long-term positioning is:

- **The open reference implementation for agent-assisted compliance work.** Not the only tool; the one the community trusts because its source is readable, its outputs are auditable, and it produces standards-compliant OSCAL alongside the formats the rest of the compliance world actually uses.
- **A standards participant.** Contribute OSCAL extensions upstream (e.g., for confidence levels on generated content). Participate in FedRAMP 20x working groups.
- **An expansion surface for adjacent frameworks.** HIPAA, PCI-DSS, ISO 27001, SOC 2. Each is an overlay on the same base architecture.
- **A possible foundation home.** By month 18, donating the project to a neutral foundation (OpenSSF, Linux Foundation, CNCF) is worth considering if contributor diversity warrants it.

This layer is not planned against. It's directional. Decisions in Layers 1 and 2 keep it possible; they don't commit to it.

---

## 5. What we optimize for at each horizon

**Hackathon (Layer 1):** A compelling 5–7 minute demo that proves the architecture. Judges remembering Efterlev the next day. A repo that looks credible to a skimmer.

**Post-hackathon (Layer 2):** First 100 GitHub stars. First external contributor PR merged. First production user citing Efterlev in a FedRAMP Moderate submission. Detection library at 80% of FedRAMP Moderate coverage. CI integration in the top 3 downloads.

**Long bet (Layer 3):** Contributor base >25 active. Used by at least three gov-contracting companies publicly. FedRAMP PMO or a 3PAO organization engaging with the tool. Cited in a government working group document.

---

## 6. The bright-line principles

These survive scope pressure at every horizon:

1. **Evidence before claims.** Deterministic scanner output is primary; LLM reasoning is secondary and flagged.
2. **Provenance always.** Nothing generated without a traceable chain to source.
3. **OSCAL as first-class output.** Internal model is our own; OSCAL is generated at the boundary for systems that consume it.
4. **Drafts, not authorizations.** The tool never claims to produce compliance.
5. **Local-first.** No telemetry, no phone-home, air-gap-viable.
6. **Extensible over monolithic.** The detector library grows via PRs; the primitive set stays small and stable.
7. **Honesty is infrastructure.** `LIMITATIONS.md` is a product feature, not a disclaimer.

---

## 7. What we do next, today

Before day 1 of the hackathon:

- [ ] Commit Apache 2.0 and push the license file
- [ ] Verify `efterlev` / `efterlev` availability on GitHub, PyPI, and npm, then create the GitHub org
- [ ] Push the repo skeleton per the directory structure in §1.1 and §2.3
- [ ] Build `demo/govnotes`
- [ ] Draft `CLAUDE.md` (done — needs update for name + OSCAL reframing + competitive landscape), `DECISIONS.md`, `LIMITATIONS.md`, `THREAT_MODEL.md`, `CONTRIBUTING.md`, `COMPETITIVE_LANDSCAPE.md`
- [ ] Download FedRAMP Moderate OSCAL baseline
- [ ] Set up MkDocs Material scaffold
- [ ] Confirm MCP server stdio setup works against an external Claude Code session

After the hackathon, within two weeks:

- [ ] Publish the demo video and the submission
- [ ] Clean up any hackathon shortcuts
- [ ] Open the first batch of "good first issue" tickets for external contributors
- [ ] Post an announcement: Hacker News, relevant Slack/Discord communities, relevant subreddits
- [ ] Set up GitHub Discussions and a project Discord

The plan is sized for one builder and Claude Code at v0–v1. It scales to a contributor community at v1–v2 if the work invites it. The architecture is the same throughout.
