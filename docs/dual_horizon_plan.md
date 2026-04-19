# Efterlev: Dual-Horizon Build Plan

**Project:** Efterlev — a repo-native, agent-first compliance scanner for FedRAMP 20x and DoD Impact Levels; KSI-native internal model; FRMR-compatible JSON as primary output; OSCAL output generators as a v1 secondary format
**Builder:** solo + Claude Code (Opus 4.7) for hackathon; growing contributor base thereafter
**License:** Apache 2.0
**Governance:** BDFL-style during v0–v1; explicit invitation to co-maintainers at 10 active contributors
**Commercial posture:** Pure OSS. Paid support and enterprise-specific features possible later; core library remains Apache 2.0 forever.

**Timing context (April 2026):** FedRAMP 20x Phase 2 Moderate is still an active pilot, extended past its original March 31, 2026 end date with authorizations like Aeroplicity's landing as recently as April 13, and wider public rollout is targeted for later in 2026.

This plan covers two horizons on a shared architecture:

- **Layer 1 — Hackathon MVP (4 days):** Tight vertical slice; demo-optimized; proves the architecture.
- **Layer 2 — Post-hackathon v1 (3–6 months):** Expansion along named axes; adoption-optimized; becomes the default OSS tool for gov-adjacent compliance automation.
- **Layer 3 — The long bet (6–18 months):** If traction materializes, becomes the open reference implementation for FedRAMP 20x's machine-readable vision.

The discipline binding the layers: **nothing built in Layer 1 is thrown away to build Layer 2.** Every architectural choice at the hackathon stage must serve the v1 target.

---

## 1. Shared architectural commitments

These hold across both horizons. They are the load-bearing decisions.

### 1.1 The detection library is a first-class concept

Not a folder of scanners inside `primitives/`. A self-contained, contribution-friendly library where each detector is an independent artifact with a defined shape: rule logic, KSI-and-control mapping, evidence template, test fixtures. A contributor can add a new detector without touching the rest of the codebase.

Detectors are capability-shaped, not control-shaped. KSIs think in capabilities (e.g., "securing network traffic"), and capability-shaped detector IDs age better than control-numbered ones as FRMR's KSI ↔ 800-53 mapping evolves.

```
detectors/
├── aws/
│   ├── encryption_s3_at_rest/
│   │   ├── detector.py         # the rule logic
│   │   ├── mapping.yaml        # KSI + 800-53 control mapping(s)
│   │   ├── evidence.yaml       # evidence template (our internal schema)
│   │   ├── fixtures/           # IaC samples that should match / should not
│   │   └── README.md           # human-readable explanation
│   └── ...
├── k8s/                        # v1 expansion
├── github_actions/             # v1 expansion (for CI-based KSIs)
└── universal/                  # KSIs that span sources
```

This structure ships in the hackathon build with six detectors. In v1, it grows via community PRs. In v2, it becomes the moat.

### 1.2 Primitive/detector/agent separation

Three distinct concepts with different contracts:

- **Detectors:** Rule-like artifacts that read source material and emit evidence candidates. Narrow, deterministic, independently testable. The community contributes these.
- **Primitives:** Typed Python functions exposed via MCP that represent agent-legible capabilities — scan an artifact using the detector library, map a KSI to its underlying controls, resolve a baseline, generate a draft attestation, validate FRMR (and in v1, OSCAL). ~15–25 in total. Stable surface area.
- **Agents:** Reasoning loops that compose primitives to accomplish a goal. Small number — Gap, Documentation, Remediation for v0; Drift, Auditor, Mapper for v1.

Detectors feed primitives. Primitives feed agents. Agents produce artifacts. Everything is provenance-tracked.

### 1.3 FRMR as primary output; OSCAL as secondary v1 output. Internal model is KSI-shaped.

The core internal data model is our own — a set of domain-shaped Pydantic types for Indicators (KSIs), Themes, Baselines, Controls (800-53), Evidence, Findings, Claims, Mappings, and Provenance that are designed around the tool's actual job. Neither FRMR nor OSCAL is the internal representation; both are produced at the output boundary.

The primary output at v0 is **FRMR-compatible JSON** — the machine-readable format FedRAMP 20x is standardizing on, vendored from `FedRAMP/docs`. OSCAL generation is a v1 secondary output format for users transitioning Rev5 submissions and for downstream consumers like RegScale's OSCAL Hub.

The reasoning:

- **Architectural alignment.** KSIs are explicitly outcome-based, measurable indicators. Our scanner model — "evidence that a capability is present, not narrative asserting that a control is implemented" — maps to KSIs natively. OSCAL's SSP narrative model was a less-good fit for what we actually produce.
- **Where FedRAMP is going.** In 2025, FedRAMP processed 100+ Rev5 authorizations with no OSCAL-structured submissions. The 20x Phase 1 Low pilot authorized 13 providers with KSIs and FRMR, not OSCAL. Our ICP is a first-FedRAMP SaaS in 2026 targeting 20x Moderate; that user is better served by KSI-native tooling than by OSCAL-native tooling.
- **Engineering simplicity.** FRMR is a single JSON file with a published JSON Schema — substantially simpler than OSCAL's nested profile/catalog/SSP model hierarchy. Less trestle wrestling; more detector library work.
- **Honest claims.** "We evidence KSI-SVC-SNT via Terraform detection" is a more honest claim than "we evidence SC-8 (whose full implementation includes procedural aspects we can't see from code)." KSIs are designed around outcomes we can genuinely detect.
- **Market positioning.** No OSS tool is KSI-native today. Comp AI is not. RegScale's depth is in OSCAL; they have architectural debt to work through on FRMR. Being early here is a real advantage.

What this looks like in practice:

- **Internal model:** Owned Pydantic types shaped around Indicators (KSIs) and Themes, with 800-53 Controls as the underlying layer that KSIs reference. Agents reason over these types, not over FRMR or OSCAL types.
- **Input side:** FRMR loaded with Pydantic directly from `catalogs/frmr/FRMR.documentation.json`; NIST 800-53 Rev 5 catalog loaded via `compliance-trestle` from `catalogs/nist/`. Both translated into the internal model at startup.
- **Output side (v0):** FRMR-compatible attestation JSON generators in `primitives/generate/`, alongside HTML and markdown. Validation against `catalogs/frmr/FedRAMP.schema.json` inside the generator.
- **Output side (v1):** OSCAL generators (Assessment Results, partial SSP, POA&M) added for Rev5 transition users and OSCAL-Hub-style consumers. Validation against NIST OSCAL schemas inside the generator.

Neither format is the internal working representation. The internal model is stable across format additions; adding a new output format is adding a generator primitive, not a rearchitecture.

### 1.4 Provenance as a queryable graph, not a log

Every claim (evidence, finding, narrative, mapping, remediation) is a node in a directed graph. Edges point from derived claims to their upstream sources. The graph is content-addressed (SHA-256 of canonical content), timestamped, and versioned — evidence records are *appended*, never overwritten.

This design serves both horizons:
- **v0:** Enables the "walk the chain from this SSP sentence back to the Terraform line" demo moment.
- **v1:** Enables "show me every KSI whose evidence has changed in the last 30 days" — the continuous monitoring story.

Storage: SQLite for the graph structure and metadata, content-addressed blob store on disk for claim content. Simple, portable, air-gap-friendly.

### 1.5 Evidence versus claims: a hard distinction

Two classes of information, treated differently throughout the system:

- **Evidence** is deterministic, scanner-derived, and high-trust. Produced by detectors. Every piece of evidence carries a raw source reference (file + line + hash).
- **Claims** are reasoned output — LLM-generated narratives, mappings, rankings, remediation proposals. Every claim carries a confidence indicator and an explicit "requires human review" flag.

The distinction is visible in the data model, the UI (when it exists), the FRMR output (and, in v1, the OSCAL output), and the provenance store. This is the defensible answer to "how does a 3PAO trust this?" The answer is: they don't trust the claims, they trust the evidence — and the claims are drafts that accelerate the human workflow.

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
- Every LLM-generated narrative carries an explicit "DRAFT — requires human review" marker in FRMR metadata (and, in v1, OSCAL metadata) and in rendered output.
- Confidence levels on generated mappings and narratives are visible, not buried.
- `LIMITATIONS.md` is a first-class document and is updated alongside feature work, not at release time.

---

## 1a. Competitive landscape and positioning

The market moved fast during planning. As of April 2026, the relevant landscape:

**Closest overlapping player — Comp AI (trycompai).** Open-source, AI-agent-driven, covers SOC 2 + ISO 27001 + HIPAA + GDPR + FedRAMP across one SaaS-first platform. 600+ customers. Their model: continuous evidence collection from 500+ SaaS integrations, AI-generated policies, OSS device agent, cloud monitoring. Their FedRAMP coverage score in their own demo is ~41% — they cover it as one framework among many, not as a focus. They do not scan Terraform source code. They do not run as a CLI in the developer's repo. They do not produce code-level remediation diffs.

**OSS OSCAL platform tier — RegScale OSCAL Hub.** Donated to the OSCAL Foundation in late 2025. Positioned as "the industry's first comprehensive, open-source platform purpose-built for working with OSCAL documents." Document-processing and review-workflow tooling for Authorizing Officials, the FedRAMP PMO, and ISSOs. This tier is taken. We are not competing with it — we are a potential *producer* of OSCAL (v1 output) that Hub consumers can review. Their architectural center of gravity is deep-OSCAL; they have real work to do to adopt FRMR and the KSI model, while we are KSI-native from day one.

**Adjacent OSS, dormant or narrow:** StrongDM Comply (SOC 2-focused policy site generator, largely dormant), 18F compliance-toolkit (OpenControl Masonry era, inactive), GoComply/fedramp (OSCAL-to-Word converter, narrow scope), mrice/complykit (2013-era license-check Maven plugin, dormant).

**What this means for our positioning:**

- We are **not** "the open-source AI compliance platform." That space has a player with real traction.
- We are **not** "the OSS OSCAL platform." That position was taken in late 2025.
- We **are** the **repo-native, agent-first, KSI-native scanner for FedRAMP 20x and DoD Impact Levels** that lives in the developer's codebase and CI pipeline, scans IaC and application source at PR-time, produces code-level findings and remediation diffs, and emits FRMR-compatible validation data for direct use with FedRAMP 20x and OSCAL (v1) for users transitioning Rev5 submissions.

The distinctions that matter:

- **Where we live.** SaaS compliance platforms live in a dashboard the compliance team opens. Efterlev lives in the repo the engineer is already in. Different locus, different UX, different buyer.
- **Who we serve first.** The primary ICP is a SaaS company (50–200 engineers) pursuing its first FedRAMP Moderate authorization, with a committed federal deal on the line. Work is owned by a DevSecOps lead or senior platform engineer. Not the GRC team (they don't have one yet); not the Authorizing Official (downstream consumer); not the defense contractor doing CMMC (v1.5+). Full profile at `docs/icp.md`.
- **Depth, not breadth.** FedRAMP Moderate + FedRAMP High + DoD IL2/4/5/6 done well beats five frameworks at 40-60% each. IL is a market Comp AI does not serve and where the government-contractor pain is most acute.
- **Claude Code and MCP as architecture, not marketing.** No competitor in our scan is built around MCP as the extension surface. The meta-loop (Claude Code builds Efterlev, Efterlev uses Claude for reasoning, external Claude Code drives Efterlev via MCP) is a unique demo and a unique architectural commitment.
- **Evidence-vs-claims discipline.** No surveyed tool has the explicit architectural distinction between deterministic scanner-derived evidence and LLM-reasoned claims. This is the defensible answer to 3PAO scrutiny that nobody else is giving.

What we retire from the pitch:
- Any framing that positions incumbents as "dashboards with workflow automation" without acknowledging Comp AI. That was the 2024 landscape.
- "OSCAL-native" as primary framing. Efterlev is KSI-native; OSCAL is a v1 secondary output for users who need it.
- Market-size claims that conflate gov-software-TAM with compliance-tooling-TAM.

What we keep:
- The thesis that compliance is an agentic workload.
- The regulatory tailwinds (FedRAMP 20x as active trajectory, OMB M-24-15, CMMC 2.0). RFC-0024's September 2026 OSCAL compliance floor is real for Rev5 transition submissions and motivates the v1 OSCAL generators; it is not the organizing principle of the project.
- The open-source commitment.
- The dev-tool-shaped positioning that nobody else is occupying.
- The KSI-native positioning that nobody else is occupying *yet*.

This section ships in the repo as `COMPETITIVE_LANDSCAPE.md` — first-class, not hidden. Judges and contributors both respect honest positioning.

---

## 2. Hackathon MVP (Layer 1) — the 4-day build

The discipline: **one vertical slice first, then replicate.** Day 1 produces a working end-to-end path for one detector. Days 2–4 replicate for five more, add agents, add polish.

### 2.1 Scope

**Six detection areas, chosen for clean IaC-detectability.** KSIs are from FRMR 0.9.43-beta (`catalogs/frmr/`):

| Detection area | KSI | 800-53 | Detection signal |
|---|---|---|---|
| Encryption at rest | `[TBD]` — closest KSI-SVC-VRI; see note | SC-28, SC-28(1) | S3/RDS/EBS encryption settings |
| Transmission confidentiality | KSI-SVC-SNT (Securing Network Traffic) | SC-8 | TLS configuration, ALB listener protocol |
| Cryptographic protection | KSI-SVC-VRI (Validating Resource Integrity) | SC-13 | Algorithms in use; FIPS mode |
| MFA enforcement | KSI-IAM-MFA (Enforcing Phishing-Resistant MFA) | IA-2 | MFA condition keys in IAM policies |
| Event logging & audit generation | KSI-MLA-LET, KSI-MLA-OSM | AU-2, AU-12 | CloudTrail scope |
| System backup | KSI-RPL-ABO (Aligning Backups with Objectives) | CP-9 | RDS automated backups; S3 versioning |

> **Note on encryption at rest:** FRMR 0.9.43-beta does not list SC-28 in any KSI's `controls` array. KSI-SVC-VRI (integrity via cryptography, nominally SC-13) is the nearest thematic fit inside the Service Configuration theme. Day 1 resolves this: either accept KSI-SVC-VRI with an honest docstring caveat, reframe the detector around integrity, or open an issue on `FedRAMP/docs` for a missing KSI. Do not invent a KSI.

**Three agents, each with a distinct reasoning task:**

- **Gap Agent:** Classifies each KSI as `implemented` / `partially implemented` / `not implemented` / `compensating` / `not applicable`, given evidence. Reasoning task: distinguishing partial from full implementation from compensating controls requires nuance a deterministic function can't handle.
- **Documentation Agent:** Drafts FRMR-compatible attestation data for each implemented or partially-implemented KSI, with every assertion carrying an evidence-ID citation. Output is KSI-structured JSON validated against `FedRAMP.schema.json`.
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
- FRMR (`FRMR.documentation.json`, `FedRAMP.schema.json`) and NIST 800-53 Rev 5 catalog vendored into `catalogs/`
- License committed, GitHub org named, repo skeleton pushed
- MkDocs Material set up for docs (empty shell is fine)

**Day 1 — one vertical slice, `aws.encryption_s3_at_rest` only, on our own model:**
- Internal Pydantic models: Indicator, Theme, Baseline, Control, Evidence, Finding, Claim, Mapping, ProvenanceRecord. Clean, small, owned.
- Detector library structure in place; one detector (`detectors/aws/encryption_s3_at_rest/`) complete with fixtures; its KSI mapping resolved (pick KSI-SVC-VRI with caveat, or raise the `[TBD]` via an issue/DECISIONS entry)
- One scan primitive (`scan_terraform`) that loads detectors and runs them
- Provenance store writing and reading claims against the internal model
- Content-addressed blob store working
- CLI: `efterlev init` and `efterlev scan`
- **End-of-day demo:** `efterlev scan ./demo/govnotes` produces findings for the one detector with provenance hashes walkable back to source. One detector, working end-to-end, on the internal model.

**Day 2 — replicate detectors; FRMR + 800-53 loading; MCP; Gap Agent:**
- Five more detectors using the pattern from day 1
- FRMR loader: Pydantic-based, reads `catalogs/frmr/FRMR.documentation.json` into our internal Indicator/Theme/Baseline model, validating against `FedRAMP.schema.json`
- 800-53 catalog loader: trestle-based, reads `catalogs/nist/NIST_SP-800-53_rev5_catalog.json` into our internal Control model. KSIs reference controls by ID; the two loaders produce a linked graph. One-way for now.
- MCP server exposing the primitive set
- External Claude Code connection tested
- Gap Agent built, invokable via CLI, producing internal GapReport objects organized by KSI
- HTML report generator for the gap report (Jinja template)
- **End-of-day demo:** `efterlev agent gap` produces a readable report across all six detection areas organized by KSI, with underlying 800-53 shown alongside, with provenance. FRMR baseline and 800-53 catalog both loaded.

**Day 3 — Documentation Agent; Remediation Agent; FRMR output generator:**
- Documentation Agent producing internal `AttestationDraft` objects with evidence citations on every assertion
- FRMR output generator: serializes `AttestationDraft` to FRMR-compatible JSON validated against `catalogs/frmr/FedRAMP.schema.json`. Validation inside the generator; no invalid FRMR ever leaves the function.
- `validate_frmr` primitive
- HTML attestation renderer alongside FRMR JSON — demo-friendly, human-readable
- Remediation Agent working for one KSI specifically — produces a diff fixing the target gap
- **End-of-day demo:** full end-to-end flow. Attestation draft generated in both FRMR JSON and HTML, with citations. Remediation diff shown.
- **Note:** OSCAL output generation is explicitly v1, not Day 3. The hackathon demo is KSI-native; OSCAL generators are a post-hackathon deliverable for Rev5 transition users.

**Day 4 — polish, docs, demo recording:**
- README written for new users (not investors)
- `docs/primitives.md` auto-generated
- Quickstart tested end-to-end from `pipx install`
- Demo video recorded mid-afternoon (NOT end of day), with retake buffer
- Submission

### 2.4 Risks and mitigations

**Risk:** FRMR validation surfaces unexpected constraints once we start generating output.
**Mitigation:** Vendored `FedRAMP.schema.json` is exercised against `FRMR.documentation.json` as part of the Day 2 loader smoke. If the schema is strict about things we haven't accounted for, we learn on Day 2, not Day 3.

**Risk:** MCP stdio transport flakes during live demo.
**Mitigation:** Pre-record the external-Claude-Code-connects-to-Efterlev moment as a fallback clip. Use it if live fails.

**Risk:** Remediation Agent produces plausible-looking but broken diffs.
**Mitigation:** Scope the demo to one target KSI/detector. Test the remediation path on day 3. If it's flaky, cut from demo video and keep in the codebase as a "coming soon" feature.

**Risk:** Scope creep during build — temptation to add the seventh detector, or to build an OSCAL generator "because it's close."
**Mitigation:** CLAUDE.md states both limits explicitly: six detection areas at v0; OSCAL generators are v1. New items require a scope-change decision logged in `DECISIONS.md`.

**Risk:** The `[TBD]` KSI mapping for encryption-at-rest produces a demo moment where we can't cleanly say which KSI is being evidenced.
**Mitigation:** Resolve on Day 1 via DECISIONS.md entry — pick KSI-SVC-VRI with honest docstring caveat, or reframe the detector around integrity. Either path is demoable; an unresolved `[TBD]` in the gap report is not.

### 2.5 Demo video structure (5–7 minutes)

1. **0:00–0:45 — Problem framing.** "Government compliance takes 18 months. Let me show you what agent-first compliance looks like."
2. **0:45–1:45 — The meta-loop.** "I built this with Claude Code. It uses Claude for reasoning. And external Claude Code sessions can drive it via MCP. Three layers of the same capability." Show a brief slide + opening clip.
3. **1:45–2:45 — Live run.** `efterlev scan` streaming findings. Click into one, walk the provenance chain to the Terraform line.
4. **2:45–3:45 — Gap report.** `efterlev agent gap`. HTML report. Highlight the evidence-vs-claims distinction.
5. **3:45–4:45 — FRMR attestation draft.** `efterlev agent document`. Show the HTML rendering of the KSI attestation with citations. Note the "DRAFT — requires human review" marker. Brief glimpse of the validated FRMR JSON alongside.
6. **4:45–5:30 — Remediation.** `efterlev agent remediate --ksi <target>`. Show the PR diff.
7. **5:30–6:15 — External Claude Code.** Separate window, Claude Code connects to Efterlev's MCP server, calls a primitive. *The architectural proof.*
8. **6:15–7:00 — The arc.** "This is week one. Here's where it goes." Brief post-hackathon roadmap slide. Thank you.

---

## 3. Post-hackathon v1 (Layer 2) — the 3–6 month build

This is where Efterlev stops being a hackathon demo and becomes a useful tool that people depend on.

### 3.1 The coverage roadmap

Expansion happens along three axes in parallel: **input sources** (what Efterlev can scan), **KSI coverage** (what it can find at the user-facing layer), and **output formats** (how it speaks to downstream tooling). Source-type expansion matters more for adoption; KSI/control depth matters more for trust; the OSCAL output generator is the major v1 format expansion for users carrying Rev5 transition submissions.

Public milestone targets, tracked in GitHub:

- **Month 1:**
  - Full audit of v0 code; refactor hackathon shortcuts
  - KSI/control coverage stays at 6 detectors, but quality per detector improves
  - **FRMR output** passes FedRAMP schema validation end-to-end (continuation of Day 3 work)
  - **OSCAL output generators land** (Assessment Results, partial SSP, POA&M). Internal `AttestationDraft` + Evidence + Claim objects serialize to OSCAL alongside FRMR. Validates against NIST OSCAL schemas before return. This is the v1 priority for users transitioning Rev5 submissions.
  - **Source expansion:** Terraform Plan JSON support (scans resolved plans including computed values); OpenTofu declared first-class alongside Terraform
- **Month 2:**
  - **+15 detectors** for Terraform/OpenTofu (total 21), prioritized by KSI coverage: additional indicators across the IAM, CMT, MLA, and SVC themes. "Proves / does not prove" documentation for each.
  - **Source expansion:** CloudFormation and AWS CDK support (CDK compiles to CloudFormation; one parser covers both). First round of detectors ported to the new source type.
  - AWS Bedrock as a second LLM backend for FedRAMP-authorized deployments (GovCloud)
- **Month 3:**
  - **+15 detectors** (total 36)
  - **Source expansion:** Kubernetes manifests + Helm charts. New KSI coverage (network policies, pod security standards, RBAC under the CNA and IAM themes).
  - Community contribution goal: first external detector PR merged
  - Tutorial on "write your own detector" published
- **Month 4:**
  - CI integration as a first-class mode. GitHub Action published. Findings-as-PR-comments working.
  - **Source expansion:** Pulumi (code-first IaC; trickier parsing, lower priority than Terraform/CloudFormation/K8s but real user demand)
- **Month 5:**
  - CMMC 2.0 overlay. Same 800-171 base as FedRAMP; CMMC-specific baseline loaded and detections mapped. Second framework shipped.
  - KSI coverage targeting ~60% of FRMR-Moderate across supported source types
- **Month 6:**
  - Drift Agent: watches a repo over time, flags when a change breaks a previously-attested KSI. Continuous monitoring delivered in a developer-facing shape.
  - KSI coverage targeting 80% of FRMR-Moderate

**v1.5 and beyond:** Runtime cloud API scanning (different threat model, needs its own design pass); ICP B becomes primary (defense contractors on CMMC 2.0 / DoD IL) with CUI handling and air-gap mode.

### 3.2 v1 agent roster

- **Drift Agent:** Monitors the provenance graph over time. Flags when evidence for a previously-implemented KSI has changed or disappeared. Emits a POA&M candidate.
- **Auditor Agent (adversarial):** Red-teams the system's own conclusions. Given a Gap Agent output, tries to find the holes — evidence that shouldn't count, narratives that overreach, mappings that are stretches. Output is a critique report.
- **Mapping Agent:** Given two baselines (e.g., FRMR Moderate and CMMC Level 2), produces a mapping with confidence levels. Uses the KSI ↔ 800-53 ↔ 800-171 graph as ground truth. Human-reviewable; a mapping accepted by a human becomes part of the shared knowledge base.

### 3.3 The knowledge base as accumulating moat

Every component contributes to a growing shared asset:

- **Detection library:** Community-contributed KSI-evidencing detectors, each with fixtures and tests.
- **Mapping library:** Human-reviewed KSI ↔ control mappings across frameworks, capturing the `[TBD]`s and the evolving relationship as FRMR matures.
- **Attestation library:** De-identified, reviewed FRMR attestation templates contributed by users who want to give back.
- **Pattern library:** IaC anti-patterns and their KSI implications.

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
- Conceptual guide: "KSIs for engineers" — explains the FedRAMP 20x model to non-compliance folks; pair with "OSCAL for engineers" for users who also need the legacy model
- Tutorial: "Add your first KSI detector"
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

- **The open reference implementation for KSI-native, agent-assisted compliance work.** Not the only tool; the one the community trusts because its source is readable, its outputs are auditable, and it produces FRMR alongside OSCAL alongside the formats the rest of the compliance world actually uses.
- **A standards participant.** Contribute to FRMR extensions upstream (e.g., for confidence levels on generated content) via `FedRAMP/docs`. Participate in FedRAMP 20x working groups. Contribute OSCAL extensions where the v1 generators surface real gaps.
- **An expansion surface for adjacent frameworks.** HIPAA, PCI-DSS, ISO 27001, SOC 2. Each is an overlay on the same base architecture.
- **A possible foundation home.** By month 18, donating the project to a neutral foundation (OpenSSF, Linux Foundation, CNCF) is worth considering if contributor diversity warrants it.

The positioning bet is explicit: Efterlev aligns with FedRAMP 20x (KSI-native) as the current trajectory, rather than trying to be the best tool for legacy Rev5 (OSCAL-native). The v1 OSCAL generators serve users bridging the transition, but the organizing principle of the project is the direction FedRAMP is actually heading.

This layer is not planned against. It's directional. Decisions in Layers 1 and 2 keep it possible; they don't commit to it.

---

## 5. What we optimize for at each horizon

**Hackathon (Layer 1):** A compelling 5–7 minute demo that proves the architecture. Judges remembering Efterlev the next day. A repo that looks credible to a skimmer.

**Post-hackathon (Layer 2):** First 100 GitHub stars. First external contributor PR merged. First production user citing Efterlev in a FedRAMP 20x Moderate authorization submission. Detection library covering 80% of FRMR-Moderate KSIs. OSCAL generators shipped and validated. CI integration in the top 3 downloads.

**Long bet (Layer 3):** Contributor base >25 active. Used by at least three gov-contracting companies publicly. FedRAMP PMO or a 3PAO organization engaging with the tool. Cited in a government working group document.

---

## 6. The bright-line principles

These survive scope pressure at every horizon:

1. **Evidence before claims.** Deterministic scanner output is primary; LLM reasoning is secondary and flagged.
2. **Provenance always.** Nothing generated without a traceable chain to source.
3. **FRMR as primary output; OSCAL as secondary v1 output.** Internal model is KSI-shaped and our own; FRMR is generated at the boundary from day one, OSCAL in v1 for systems that consume it.
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
- [ ] Draft `CLAUDE.md`, `DECISIONS.md`, `LIMITATIONS.md`, `THREAT_MODEL.md`, `CONTRIBUTING.md`, `COMPETITIVE_LANDSCAPE.md`
- [ ] Vendor FedRAMP FRMR content from `FedRAMP/docs` into `catalogs/frmr/`
- [ ] Vendor NIST SP 800-53 Rev 5 catalog from `usnistgov/oscal-content` into `catalogs/nist/`
- [ ] Set up MkDocs Material scaffold
- [ ] Confirm MCP server stdio setup works against an external Claude Code session

After the hackathon, within two weeks:

- [ ] Publish the demo video and the submission
- [ ] Clean up any hackathon shortcuts
- [ ] Open the first batch of "good first issue" tickets for external contributors
- [ ] Post an announcement: Hacker News, relevant Slack/Discord communities, relevant subreddits
- [ ] Set up GitHub Discussions and a project Discord

The plan is sized for one builder and Claude Code at v0–v1. It scales to a contributor community at v1–v2 if the work invites it. The architecture is the same throughout.
