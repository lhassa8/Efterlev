# Efterlev

**Compliance automation for SaaS companies pursuing their first FedRAMP Moderate authorization via the FedRAMP 20x pilot.**

Scans your Terraform for KSI-level evidence. Drafts FRMR-compatible validation data for your 3PAO. Proposes code-level remediations you can apply today. Runs locally — no SaaS, no telemetry, no procurement cycle.

Built for the VP Eng or DevSecOps lead whose CEO just told them "we need FedRAMP" and who needs to know, by Monday, where they actually stand.

Pronounced "EF-ter-lev." From Swedish *efterlevnad* (compliance).

```bash
pipx install efterlev
cd your-repo
efterlev init --baseline fedramp-20x-moderate
efterlev scan
```

> **Status (April 2026): v0 shipped; v1 closed-development.** Six detectors, three agents (Gap, Documentation, Remediation), MCP stdio server, full provenance graph, HTML report rendering for every agent output, end-to-end CI demo running against a sample FedRAMP Terraform repo on GitHub Actions. The repository is private through v1 development (closed-source, no public announcement); security-team review access for evaluating customers is granted via private-repo invite under NDA. License is Apache 2.0; public-release timing will be revisited at first customer engagement or Month 6. See [Project status](#project-status) for specifics of what's in and what's next.

Efterlev is **KSI-native**: its primary abstraction is the Key Security Indicator from FedRAMP 20x, with 800-53 Rev 5 controls as the underlying reference. Agent-drafted outputs (gap classifications, attestation narratives, remediation diffs) are emitted as self-contained HTML reports at v0; a FRMR-compatible attestation-JSON generator is the first v1 deliverable — the internal model is already FRMR-shaped. OSCAL output for Rev5-transition submissions is deferred to v1.5+, gated on customer pull (see `DECISIONS.md` 2026-04-22).

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

### A primer for the unfamiliar

The U.S. federal government buys software through a process called **FedRAMP** (Federal Risk and Authorization Management Program). Before a federal agency can use your SaaS product, the product has to be authorized at one of three levels — Low, Moderate, or High — based on the sensitivity of the data it handles. Most SaaS authorizations target Moderate.

Historically, getting authorized meant: hire a specialist consultant ($250K+), spend 12–18 months producing a thousand-plus-page document called a **System Security Plan (SSP)**, get assessed by a **3PAO** (Third-Party Assessment Organization, an independent auditor accredited to evaluate FedRAMP packages), and submit the result to the FedRAMP PMO (Program Management Office) for review.

In 2026 this is changing. **FedRAMP 20x** is the new authorization track, and it replaces narrative-heavy SSPs with measurable outcomes called **Key Security Indicators (KSIs)** — concrete things like "encrypt network traffic" and "enforce phishing-resistant MFA" that can be assessed against actual evidence rather than long descriptions of intent. The machine-readable format for that evidence is **FRMR** (FedRAMP Machine-Readable). New SaaS authorizations starting in 2026 are heading into the 20x track.

Efterlev exists for the SaaS company landing in this exact moment.

### The story

A 100-person SaaS company just got told by its biggest prospect: "we'll buy, but only if you're FedRAMP Moderate by next year."

The team looks at each other. Nobody has done this before. They google it and find:

- Consulting engagements starting at $250K
- SaaS compliance platforms that cover SOC 2 beautifully but treat FedRAMP as a footnote
- Enterprise GRC tooling priced for the wrong scale
- Spreadsheets, Word templates, and a NIST document family that runs to thousands of pages

What they actually need is something that reads their Terraform (the code that defines their cloud infrastructure) and tells them, in their own language, what's wrong and how to fix it. Something a single engineer can install on a Tuesday and show results at Wednesday's standup. Something whose output is concrete enough that their 3PAO can use it — and whose claims are honest enough that the 3PAO won't throw it out.

Efterlev is that tool. It runs where the engineer already is (the repo, the CLI, the CI pipeline). It produces FRMR from day one — the machine-readable format FedRAMP 20x is standardizing on, and the format most new SaaS authorizations in 2026 will target — with OSCAL support on the v1 roadmap for users carrying older Rev5 transition submissions. It refuses to overclaim, because 3PAOs don't trust tools that do.

As of April 2026, the FedRAMP 20x Phase 2 Moderate pilot is still active past its original March 31, 2026 end date, with authorizations like Aeroplicity's landing as recently as April 13, and wider public rollout targeted for later in 2026 — the trajectory Efterlev's KSI-native posture is aligned with.

It's also deliberately deep rather than broad. FedRAMP 20x Moderate first; DoD Impact Levels (the framework for Department of Defense workloads) and CMMC 2.0 (the framework for ~300,000 defense contractors) on the v1 roadmap. Not SOC 2, not ISO 27001, not HIPAA — there are tools that serve those well, and our value is depth in gov-grade frameworks, not breadth across every compliance acronym.

See [COMPETITIVE_LANDSCAPE.md](./COMPETITIVE_LANDSCAPE.md) for where Efterlev fits among existing tools.

---

## How it works

A walk through what happens when you use Efterlev.

**1. You point it at your repo.** Efterlev runs locally on your machine. You install it (`pipx install efterlev`), `cd` into the directory holding your Terraform code, and configure it once.

**2. It scans.** A library of small, deterministic rules called *detectors* reads your `.tf` files and looks for compliance-relevant patterns: is this S3 bucket encrypted? does this load balancer enforce TLS? does this IAM policy require MFA? Each finding is a concrete piece of *evidence* — a fact about your code, with a file path and line number you can verify yourself. No AI is involved at this step; the same input always produces the same output.

**3. The Gap Agent reads the evidence.** This is where AI enters. Claude reads what the scanner found and produces a status report: for each Key Security Indicator, are you implemented, partially implemented, or not implemented? You get a human-readable HTML report.

**4. The Documentation Agent drafts attestations.** For each KSI you want to assert, this agent writes the FRMR-compatible JSON your 3PAO will review. Every assertion cites the evidence it's based on. The output is marked **"DRAFT — requires human review"** so nobody mistakes it for a finished product.

**5. The Remediation Agent suggests fixes.** Pick a finding (say, an unencrypted S3 bucket) and this agent proposes a Terraform change that closes the gap. You review the diff, then apply it yourself. Efterlev never modifies your code without your action.

**6. You can walk the chain.** Anything Efterlev produces — a draft sentence, a status classification, a remediation diff — can be traced back through the AI's reasoning step, the evidence it cited, and the Terraform line that produced that evidence. If the chain breaks down, you know not to trust the output.

That's it. No dashboard, no SaaS sign-up, no waiting on procurement. The whole flow is local; the AI calls go to your configured LLM endpoint (you control the data); the outputs land as files you can review, edit, or hand to your consultant.

---

## How it's built

**Three layers, each with a clear job.**

**Detectors** — the eyes. Each detector is a small, self-contained Python folder with one job: "look for this specific compliance-relevant pattern in this kind of source file." We ship six at v0; the long-term plan is hundreds. Detectors are deterministic — they do not use AI. Anyone can write a new detector without touching the rest of the codebase, which is what makes the detector library a community-contributable asset.

**Primitives** — the verbs. About 15–25 typed functions that wrap the things agents need to do: "scan this directory," "load that catalog," "validate this output against the schema." Primitives are the small, stable interface layer. They do the mechanical work cleanly so the agents can focus on reasoning.

**Agents** — the reasoners. Three at v0 (Gap, Documentation, Remediation). Each is a focused loop: take the evidence (and any related context), call Claude with a carefully written system prompt, produce a typed artifact. Every agent's system prompt lives in a plain `.md` file in the repo, so you can read exactly how each agent is instructed and audit how the prompts change over time.

### How AI is used

We use Claude for the parts where reasoning matters: classifying whether a control is implemented, drafting compliance narrative, proposing code changes. We do **not** use AI for the parts where determinism matters: the scanners, the schema validation, the provenance tracking.

**Model selection is per-agent**, tuned to the shape of each agent's task:

- **Gap Agent** → `claude-opus-4-7`. Classification requires judgment calls on ambiguous evidence and the discipline to refuse to borrow evidence from unrelated KSIs. Cheaper models drift on the honesty posture.
- **Documentation Agent** → `claude-sonnet-4-6`. Structured extractive writing against a strict format contract. Sonnet handles it at roughly 1/5 the cost per token with no quality delta observed in the reference CI runs. 60 narratives per full-baseline run: ~$1 on Sonnet versus ~$4-5 on Opus.
- **Remediation Agent** → `claude-opus-4-7`. Generating syntactically valid Terraform diffs grounded in real source plus naming what the diff does NOT cover is code-generation plus architectural judgment. Opus-grade.

See [DECISIONS.md](./DECISIONS.md) for the full rationale. Callers override per-call via the `model` arg on each agent; the framework is already built to swap in AWS Bedrock as a second backend in v1 without touching agent code.

This split — **deterministic for evidence, AI for reasoning, different model weights for different cognitive loads** — is the most important design decision in the project. It's what lets us tell auditors and 3PAOs the truth: scanner findings are verifiable facts about your code; AI claims are drafts you can audit but should not blindly trust.

**Hallucination defenses are structural, not advisory.** Every AI-generated claim links explicitly to the evidence records it was reasoning over via content-addressed IDs. Every agent prompt wraps evidence in `<evidence id="sha256:...">...</evidence>` XML fences; a post-generation validator rejects any output that cites evidence IDs not present as fences in the prompt the model actually saw (see [DECISIONS 2026-04-21 design call #3](./DECISIONS.md)). Every claim carries a "DRAFT — requires human review" marker that cannot be removed by a configuration flag — it's a `Literal[True]` at the type level, not a string. This is enforced at the type-system level, not by convention.

### Provenance is automatic and complete

Every detector finding, every AI claim, every remediation suggestion is stored as a node in a local graph (SQLite plus a content-addressed file store under `.efterlev/`). Edges point from derived claims to their sources. The graph is **append-only** — new evidence does not overwrite old, it adds. You can trace any output sentence back to the file and line that produced it with a single CLI command (`efterlev provenance show <id>`).

### MCP makes Efterlev pluggable

**MCP** (Model Context Protocol) is how AI agents discover and call tools. Efterlev exposes its primitives via an MCP server, which means any MCP-capable AI tool — including a fresh Claude Code session running in your editor — can drive Efterlev directly. You can build your own compliance workflow on top of Efterlev's primitives without forking the codebase. Our own agents use the same MCP interface, which is how we know it actually works.

### The stack

Python 3.12, Pydantic v2 for typed I/O, Typer for the CLI, `compliance-trestle` for loading the NIST 800-53 catalog, `python-hcl2` for parsing Terraform, the official MCP Python SDK for the server, the Anthropic Python SDK for Claude calls. AWS Bedrock as a second LLM backend is committed for v1 (so the tool can run inside FedRAMP-authorized GovCloud environments). Apache 2.0 throughout.

For deeper architectural detail, see [docs/architecture.md](./docs/architecture.md). For the design history and reversals, see [DECISIONS.md](./DECISIONS.md).

---

## Quickstart

### Install

```bash
pipx install efterlev
```

Requires Python 3.12+. `uv` is used internally but not required for end users.

While the repository is private (pre-public-tag), install from a cloned checkout or directly from git:

```bash
# from a checkout
pip install -e .

# or from git, using a fine-grained PAT with Contents:read on this repo
pip install "git+https://x-access-token:${EFTERLEV_INSTALL_TOKEN}@github.com/lhassa8/Efterlev.git@main"
```

The govnotes-demo reference CI uses exactly this pattern — see [its workflow](https://github.com/lhassa8/govnotes-demo/blob/main/.github/workflows/efterlev-scan.yml) for a working install + scan + agent pipeline.

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

The Gap Agent (Claude Opus 4.7) classifies each KSI as implemented, partial, not_implemented, or not_applicable, given the evidence collected. Underlying 800-53 control status is shown alongside. Requires `ANTHROPIC_API_KEY`. Writes a self-contained HTML report to `.efterlev/reports/gap-<timestamp>.html` and prints the per-KSI summary to the terminal. Every classification is persisted as a Claim record in the provenance store.

### Draft attestation narratives

```bash
efterlev agent document                     # all classified KSIs
efterlev agent document --ksi KSI-SVC-SNT   # one KSI
```

The Documentation Agent (Claude Sonnet 4.6 by default — see [DECISIONS.md](./DECISIONS.md) for the per-agent model-selection rationale) drafts an attestation narrative per classified KSI, grounded in the evidence the Gap Agent cited. Every narrative cites evidence by ID, names what the scanner proved and what it did not. Output is `.efterlev/reports/documentation-<timestamp>.html` with one card per KSI. Cost is typically ~$1-2 for a full baseline; at ~$0.02 per KSI narrative. FRMR-compatible JSON serialization is a v1 deliverable — the internal `AttestationDraft` model is already FRMR-shaped, it's the serializer that's next.

### Propose remediation

```bash
efterlev agent remediate --ksi KSI-SVC-SNT
```

The Remediation Agent (Claude Opus 4.7) proposes a `git apply`-ready Terraform diff that closes the gap for one KSI, reading the `.tf` files the evidence referenced. Output is `.efterlev/reports/remediation-<ksi>-<timestamp>.html` with the diff in a monospace block, the explanation of what it changes and what it does NOT cover, and step-by-step "how to apply" guidance. Efterlev never modifies your code; a human reviews the diff and decides.

### Walk the provenance

```bash
efterlev provenance show <record_id>
```

Every generated claim traces back through the reasoning step, the evidence records cited, to the Terraform file and line that produced the evidence. Record IDs are printed by every command for exactly this purpose.

### Run over MCP

```bash
efterlev mcp serve
```

Exposes every CLI verb as an MCP tool over stdio. Point Claude Code (or any MCP client) at it to drive scans, agent calls, and provenance walks from another AI session. Every tool call is logged as an `mcp_tool_call` Claim record in the target repo's provenance store; see [THREAT_MODEL.md](./THREAT_MODEL.md) T6 for the trust model.

---

## Current coverage

### Input sources (v0)

Efterlev v0 scans **Terraform and OpenTofu** source files (`.tf`). It does not scan CloudFormation, AWS CDK, Pulumi, Kubernetes manifests, or live cloud infrastructure. Each of those is on the v1 roadmap below.

If your FedRAMP boundary is Terraform-primary, Efterlev works for you today. If you're deep in CloudFormation or CDK, hold off — v1 is not far.

### FedRAMP 20x KSIs and underlying 800-53 controls (v0)

KSIs below are from FRMR 0.9.43-beta (vendored at `catalogs/frmr/`). Each detection area evidences the listed KSI(s) and the 800-53 controls the KSI references.

| Detector | KSI (FRMR 0.9.43-beta) | 800-53 | Resource types |
|---|---|---|---|
| `aws.encryption_s3_at_rest` | (unmapped in FRMR — see note below) | SC-28, SC-28(1) | `aws_s3_bucket`, `aws_s3_bucket_server_side_encryption_configuration` |
| `aws.tls_on_lb_listeners` | **KSI-SVC-SNT** (Securing Network Traffic) | SC-8 | `aws_lb_listener`, `aws_alb_listener` |
| `aws.fips_ssl_policies_on_lb_listeners` | **KSI-SVC-VRI** (Validating Resource Integrity); reinforces KSI-SVC-SNT | SC-13 | `aws_lb_listener`, `aws_alb_listener` |
| `aws.mfa_required_on_iam_policies` | **KSI-IAM-MFA** (Enforcing Phishing-Resistant MFA) | IA-2 | `aws_iam_{policy,role_policy,user_policy,group_policy}` |
| `aws.cloudtrail_audit_logging` | **KSI-MLA-LET** (Logging Event Types), **KSI-MLA-OSM** (Operating SIEM Capability) | AU-2, AU-12 | `aws_cloudtrail` |
| `aws.backup_retention_configured` | **KSI-RPL-ABO** (Aligning Backups with Objectives) | CP-9 | `aws_db_instance`, `aws_rds_cluster`, `aws_s3_bucket_versioning` |

> **Note on SC-28 (encryption at rest).** FRMR 0.9.43-beta does not list SC-28 in any KSI's `controls` array. Per [DECISIONS 2026-04-21 design call #1](./DECISIONS.md), the detector declares `ksis=[]` rather than shoehorning SC-28 into a thematically-adjacent KSI (we considered KSI-SVC-VRI — integrity via crypto — but rejected it since SC-28 is specifically about confidentiality at rest, not integrity). The evidence still surfaces in the gap report's **Unmapped findings** section, honest about the current FRMR mapping gap. We expect this to resolve as FRMR moves from beta toward GA.

> **Note on KSI-IAM-MFA.** The indicator requires *phishing-resistant* MFA. Our detector evidences that MFA is enforced via IAM policy condition keys (`aws:MultiFactorAuthPresent`), which is MFA presence but not phishing resistance. The phishing-resistance layer lives in IdP configuration (Okta, Entra, Cognito) and is procedural — outside what a scanner can see. The detector README and every per-KSI narrative calls this out explicitly.

> **Note on policy documents built with `jsonencode`.** `python-hcl2` renders `jsonencode({...})` and `data.aws_iam_policy_document.X.json` as `${...}` placeholders rather than resolved JSON. The MFA detector flags these as `mfa_required=unparseable`; the Gap Agent classifies such cases as `partial` with the honest "cannot confirm or refute" narrative rather than a false positive.

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

## Integrating with Claude Code

Efterlev exposes its primitives via an MCP server. Point any Claude Code session at it and Claude can discover and call every primitive directly.

```bash
efterlev mcp serve
```

In your Claude Code settings, add the server. Claude can now scan your repo, walk provenance, draft narratives, or propose remediations as part of a broader coding session — the same capabilities Efterlev's own agents use, available to yours.

This also means: if you want to build a compliance workflow Efterlev doesn't ship, you don't need to fork Efterlev. Write your own agent against the MCP interface.

---

## Project status

**Current state: v0 shipped. Repository private; first public tag pending hardening + credential rotation.**

### What v0 contains

**Pipeline.** `init → scan → agent gap → agent document → agent remediate → provenance show` runs end-to-end. Every CLI verb is also an MCP tool.

**Detectors (6).** `aws.encryption_s3_at_rest`, `aws.tls_on_lb_listeners`, `aws.fips_ssl_policies_on_lb_listeners`, `aws.mfa_required_on_iam_policies`, `aws.cloudtrail_audit_logging`, `aws.backup_retention_configured`. All self-contained under `src/efterlev/detectors/aws/<capability>/` with detector.py, mapping.yaml, evidence.yaml, fixtures/, and README.md. Each detector's README names what it proves and what it does not.

**Agents (3).** Gap (Opus 4.7), Documentation (Sonnet 4.6), Remediation (Opus 4.7). Each has its system prompt in a sibling `.md` file — see `src/efterlev/agents/*_prompt.md`. Prompts include explicit evidence-fencing rules and cite-by-fenced-id discipline.

**Primitives (2 deterministic so far).** `scan_terraform`, `generate_frmr_skeleton`. Both `@primitive`-registered and MCP-exposed. `generate_frmr_skeleton` produces a scanner-only `AttestationDraft` from evidence — the deterministic half of FRMR attestation assembly, usable standalone without any LLM call.

**Provenance.** SQLite index + content-addressed blob store + append-only JSONL receipt log under `.efterlev/`. Every record (Evidence, Claim, ProvenanceRecord) is content-addressed by SHA-256. `efterlev provenance show <record_id>` walks the chain.

**Output surface.** Self-contained HTML reports under `.efterlev/reports/`: gap-\<ts\>.html, documentation-\<ts\>.html, remediation-\<ksi\>-\<ts\>.html. Inline CSS, no JavaScript, no external fonts — portable, emailable, archivable. Evidence records render with a green left border; Claims render amber with the DRAFT banner. That visual split is the trust-class discipline made visible.

**MCP server.** stdio transport, stateless, self-logging. 7 tools: `efterlev_init`, `efterlev_scan`, `efterlev_agent_gap`, `efterlev_agent_document`, `efterlev_agent_remediate`, `efterlev_provenance_show`, `efterlev_list_primitives`. Every tool invocation writes one `mcp_tool_call` claim record into the target repo's provenance store before dispatching. See [THREAT_MODEL.md](./THREAT_MODEL.md) T6.

**CI proof.** End-to-end demo runs on every PR to [lhassa8/govnotes-demo](https://github.com/lhassa8/govnotes-demo) (public demo-target repo) using the workflow at `.github/workflows/efterlev-scan.yml`. Workflow installs Efterlev from this private repo, runs the full pipeline against real Terraform, and uploads gap + documentation + remediation HTML artifacts.

**Tests.** 238 passing. `ruff check` + `ruff format --check` + `mypy --strict` clean across 70 source files. `pytest`, `ruff`, `mypy` run on every push via GitHub Actions.

### What v0 does NOT contain yet

- **FRMR-compatible JSON serialization** of `AttestationDraft` records. The internal model is FRMR-shaped; the serializer primitive is v1. v0 emits HTML only.
- **OSCAL output generators.** v1. `compliance-trestle` is used for 800-53 catalog *input* today.
- **Non-Terraform input sources.** v0 is `.tf` files only. No CloudFormation, CDK, Pulumi, Kubernetes, runtime cloud APIs.
- **More detectors.** Six is the MVP set. The detector library is designed to grow — a new detector is one folder plus one import line.
- **Public package on PyPI.** Install is from git while the repo is private.

### Stable surface

Designed to not break once shipped publicly:

- `@detector` and `@primitive` decorator contracts
- Evidence / Claim / ProvenanceRecord / AttestationDraft Pydantic models
- CLI verb names and argument shapes
- MCP tool names and JSON Schemas
- `.efterlev/` on-disk layout

### Changing surface

- Detector content (as more land)
- Agent system prompts (as they're tuned)
- FRMR JSON output shape (serializer arrives in v1)
- OSCAL generators (v1)

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
- [docs/scope.md](./docs/scope.md) — v0 MVP scope contract
- [docs/day1_brief.md](./docs/day1_brief.md) — quick-reference for Day 1 of the hackathon
- [LIMITATIONS.md](./LIMITATIONS.md) — what Efterlev does and doesn't do
- [THREAT_MODEL.md](./THREAT_MODEL.md) — security posture
- [COMPETITIVE_LANDSCAPE.md](./COMPETITIVE_LANDSCAPE.md) — honest positioning against Comp AI, RegScale OSCAL Hub, and others
- [DECISIONS.md](./DECISIONS.md) — architectural decision log
- [CONTRIBUTING.md](./CONTRIBUTING.md) — contributor onboarding
