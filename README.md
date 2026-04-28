# Efterlev

**Compliance automation for SaaS companies pursuing their first FedRAMP Moderate authorization via the FedRAMP 20x pilot.**

Scans your Terraform for KSI-level evidence. Drafts FRMR-compatible validation data for your 3PAO. Proposes code-level remediations you can apply today. Runs locally — no SaaS, no telemetry, no procurement cycle.

Built for the VP Eng or DevSecOps lead whose CEO just told them "we need FedRAMP" and who needs to know, by Monday, where they actually stand.

Pronounced "EF-ter-lev." From Swedish *efterlevnad* (compliance).

```bash
# Pre-launch — install from a cloned checkout. `pipx install efterlev`
# lands at v0.1.0; until then, this is the only working path.
git clone https://github.com/efterlev/efterlev.git
cd efterlev
uv sync --extra dev
cd /path/to/your-repo
uv run efterlev init --baseline fedramp-20x-moderate

# If your Terraform composes upstream modules (the dominant pattern),
# scan the resolved plan rather than the raw .tf files — detectors
# don't follow module sources without it. See Quickstart > Scan below.
terraform init && terraform plan -out plan.bin && terraform show -json plan.bin > plan.json
uv run efterlev scan --plan plan.json

# OR — if your Terraform is mostly raw `resource` declarations:
uv run efterlev scan
```

Once v0.1.0 publishes to PyPI, `pipx install efterlev` becomes the
primary install path. PyPI release is part of the pre-launch
distribution-readiness gate; see the "Status" block below for where
that sits.

> **Status (April 2026): v0 shipped; v1 Phase 1 + Phase 2 + Plan JSON + dogfood coverage-followup + prompt hardening + GitHub Action + POA&M generator landed. Open-source-first posture locked; all eight pre-launch readiness gates closed at the spec level (2026-04-25); destination-repo operational setup complete (transfer, branch ruleset, Pages, DCO bot, environments, both Trusted Publishers, signed-commit flow validated end-to-end) and the release pipeline validated via 5 successive rc-tag dry-runs that found + fixed 5 real bugs (2026-04-26). Repo flips public after the remaining maintainer-action items (security-review §8 sign-off, 24-hour fresh-eyes pause, optional GovCloud walkthrough, then `git tag v0.1.0`).**
> - **v0:** six AWS-Terraform detectors, three agents (Gap, Documentation, Remediation), MCP stdio server, full provenance graph, HTML reports. Phase 6-lite + dogfood coverage-follow-up + A4 detector-breadth gate bring the detector count to **30** (16 added in A4 covering SC-7 network-boundary, SI-4/AU-2 monitoring, SC-12/SC-28 key management, IA-2/AC-6 IAM-depth, and AU-2/AU-12 ELB-logging families).
> - **v1 Phase 1 (Evidence Manifests):** customers declare procedural attestations in `.efterlev/manifests/*.yml`; they flow into the Gap Agent alongside detector Evidence. Takes scanner-only coverage from ~20% of the FedRAMP Moderate baseline toward 80%+ when paired with detectors.
> - **v1 Phase 2 (FRMR attestation generator):** `efterlev agent document` emits an FRMR-compatible attestation JSON artifact alongside the HTML report — the v1 primary production output.
> - **Plan JSON scan mode:** `efterlev scan --plan plan.json` reads `terraform show -json` output, giving detectors ~60% more evidence in `for_each`/module-heavy codebases than static `.tf` parsing.
> - **Secret redaction + retry/fallback:** every LLM prompt is unconditionally scrubbed for 7 secret families (AWS, GCP, GitHub, Slack, Stripe, PEM, JWT) before egress; `efterlev redaction review` audits what was redacted per scan. Anthropic calls retry with exponential backoff + full jitter and fall back from Opus to Sonnet once before surfacing a failure.
> - **POA&M generator:** `efterlev poam` emits a reviewer-ready Plan of Action & Milestones markdown for every open KSI. OSCAL-shaped POA&M JSON remains v1.5+.
> - **CI integration:** `.github/workflows/pr-compliance-scan.yml` is a drop-in GitHub Action that scans PRs, posts a sticky markdown comment with findings + detector coverage, and uploads the `.efterlev/` artifact. See [docs/ci-integration.md](./docs/ci-integration.md).
> - **Open-source-first posture (2026-04-23):** rescinds the 2026-04-22 closed-source-through-v1 lock. Efterlev will be a pure-OSS Apache-2.0 public repository. Launch is gate-driven — eight pre-launch readiness gates cover identity/governance, distribution (PyPI + container + GitHub Action marketplace), AWS Bedrock backend for GovCloud deployability, detector breadth to 30, trust surface, documentation site, deployment-mode verification, and launch rehearsal. No managed tier, no paid layer, no commercial edition — the project stays pure OSS. See `DECISIONS.md` 2026-04-23 "Rescind closed-source lock."
>
> The repository is pre-launch private today; the launch commitment is public Apache-2.0 once every readiness gate passes. License is Apache 2.0 throughout; private-repo visibility is purely a pre-launch staging posture, not a reversible distribution model. See `DECISIONS.md` 2026-04-23 for the open-source commitment and `CLAUDE.md` for the current-state summary.

Efterlev is **KSI-native**: its primary abstraction is the Key Security Indicator from FedRAMP 20x, with 800-53 Rev 5 controls as the underlying reference. Agent outputs (gap classifications, attestation narratives, remediation diffs) render as self-contained HTML reports; the Documentation Agent additionally emits an FRMR-compatible attestation JSON artifact consumable by 3PAOs and downstream tooling. OSCAL output for Rev5-transition submissions is deferred to v1.5+, gated on customer pull (see `DECISIONS.md` 2026-04-22).

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

**1. You point it at your repo.** Efterlev runs locally on your machine. You install it (today: `uv sync --extra dev` against a cloned private repo; v1 release plan: `pipx install efterlev` once the repo opens), `cd` into the directory holding your Terraform code, and configure it once.

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

**Hallucination defenses are structural, not advisory.** Every AI-generated claim links explicitly to the evidence records it was reasoning over via content-addressed IDs. Every agent prompt wraps evidence in `<evidence id="sha256:...">...</evidence>` XML fences; a post-generation validator rejects any output that cites evidence IDs not present as fences in the prompt the model actually saw (see [DECISIONS 2026-04-21 design call #3](./DECISIONS.md)). Defense-in-depth runs at the store layer too: `ProvenanceStore.write_record` refuses to persist a Claim whose `derived_from` cites ids not resolvable against the store, so a buggy agent or direct write path cannot create a citation that doesn't land. Every claim carries a "DRAFT — requires human review" marker that cannot be removed by a configuration flag — it's a `Literal[True]` at the type level, not a string. This is enforced at the type-system level, not by convention.

**Secrets never leave the machine unredacted.** Before every LLM call, Efterlev scrubs the prompt for seven secret families — AWS access keys, GCP API keys, GitHub tokens, Slack tokens, Stripe keys, PEM private keys, JWTs — replacing matches with `[REDACTED:family:sha256-prefix]` placeholders. The scrubber is unconditional (no feature flag, no way for an agent author to disable it) and runs on detector Evidence, source-file fences, and free-text narratives alike. Each redaction writes a line to `.efterlev/redactions/<scan_id>.jsonl` (mode `0o600`) with the family, a truncated preview, and the record id it came from; `efterlev redaction review` renders that log. The failure mode is conservative over-redaction, not silent leakage.

**LLM calls degrade predictably.** Transient Anthropic errors (rate-limit, timeout, overloaded, connection reset) retry with exponential backoff plus full jitter, up to three attempts on the primary model. If the primary model exhausts its retries, the client falls back once to a configured secondary (Opus 4.7 → Sonnet 4.6 by default) before surfacing the failure. Non-retryable errors (authentication, invalid request) fail immediately. The retry loop is unit-tested with an injectable sleeper so the behaviour is verifiable without waiting on real clock time.

### Provenance is automatic and complete

Every detector finding, every AI claim, every remediation suggestion is stored as a node in a local graph (SQLite plus a content-addressed file store under `.efterlev/`). Edges point from derived claims to their sources. The graph is **append-only** — new evidence does not overwrite old, it adds. You can trace any output sentence back to the file and line that produced it with a single CLI command (`efterlev provenance show <id>`).

### MCP makes Efterlev pluggable

**MCP** (Model Context Protocol) is how AI agents discover and call tools. Efterlev exposes its primitives via an MCP server, which means any MCP-capable AI tool — including a fresh Claude Code session running in your editor — can drive Efterlev directly. You can build your own compliance workflow on top of Efterlev's primitives without forking the codebase. Our own agents use the same MCP interface, which is how we know it actually works.

### The stack

Python 3.12, Pydantic v2 for typed I/O, Typer for the CLI, `compliance-trestle` for loading the NIST 800-53 catalog, `python-hcl2` for parsing Terraform, the official MCP Python SDK for the server, the Anthropic Python SDK for direct Claude calls, and `boto3` for the AWS Bedrock backend (so the tool runs inside FedRAMP-authorized GovCloud environments without egress to `anthropic.com`). The Bedrock backend opts in via `pipx install 'efterlev[bedrock]'` or the container image; default install stays lean for non-GovCloud users. Apache 2.0 throughout.

For deeper architectural detail, see [docs/architecture.md](./docs/architecture.md). For the design history and reversals, see [DECISIONS.md](./DECISIONS.md).

---

## Quickstart

### Install

**Pre-launch today: install from a cloned checkout.** The package
(currently `0.0.1rc5`) is not yet published to PyPI; `pipx install
efterlev` becomes the primary install path once v0.1.0 lands and the
pre-launch distribution-readiness gate (A2 in the open-source launch
plan) closes. Until then:

```bash
# from a cloned checkout:
git clone https://github.com/efterlev/efterlev.git
cd efterlev
uv sync --extra dev

# or with pip, if you can't use uv:
pip install -e .
```

Requires Python 3.12+. `uv` is used throughout the repo for dependency
management; dev, lint, type-check, and test commands run through it.

**Launch plan:** `pipx install efterlev` from PyPI; `ghcr.io/efterlev/efterlev`
container image for Docker / Kubernetes / GovCloud-EC2 runs; composite
GitHub Action at `efterlev/scan-action` for CI. All artifacts will be
Sigstore-signed. The repo flips to public Apache-2.0 once every launch
readiness gate passes — no scheduled date, launch is gate-driven. See
`DECISIONS.md` 2026-04-23 "Rescind closed-source lock" for the posture
commitment and the eight readiness gates.

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
efterlev scan --plan plan.json             # module-composed codebases (the dominant pattern)
efterlev scan                              # raw `resource` declarations only
```

Runs all applicable detectors against your Terraform. Produces findings with full provenance. Scanner-only — no LLM calls, no network; FRMR and 800-53 catalogs are loaded from the local `catalogs/` directory.

**Pick the path that matches your codebase.** Most ICP-A Terraform composes upstream modules (`module "eks" { source = "terraform-aws-modules/eks/aws" ... }`); the actual workload — EKS clusters, VPCs, IAM roles, KMS keys, security groups, CloudTrail — lives inside those modules. Detectors look at root-level `resource` declarations only, so module-composed codebases need plan-JSON expansion to surface their resources.

#### Module-composed (the dominant pattern)

```bash
terraform init
terraform plan -out plan.bin
terraform show -json plan.bin > plan.json
efterlev scan --plan plan.json
```

`terraform show -json` resolves every `for_each`, `count`, and module expansion into concrete resources. The detector library sees ~60% more evidence than HCL mode against real-world codebases (`docs/dogfood-2026-04-22.md` has the measured lift; `docs/dogfood-findings-2026-04-27.md` has a worked example where HCL mode produced 1 evidence record and plan-JSON would produce ≥10).

If your plan fails on "for_each argument derived from apply-time results" because the `buckets` map (or similar) contains `(known after apply)` values, you're in the first-plan-after-init case: `terraform apply -target=<prereq>` the prerequisite resources first, then re-plan. This matches standard Terraform-CI practice.

#### Raw `resource` declarations only

```bash
efterlev scan
```

Parses `.tf` files statically via python-hcl2. Fast, no Terraform CLI dependency, no AWS credentials required. Use this when your Terraform is mostly raw `resource "aws_*" {}` blocks rather than `module {}` invocations — small workloads, demo fixtures, single-purpose modules.

When the scanner detects a module-composed codebase being scanned in HCL mode (a common honest-mistake), it emits a structured warning at scan time recommending plan-JSON expansion with the exact command sequence above. Exit code stays 0 — the scan succeeded; coverage is just limited.

### Analyze

```bash
efterlev agent gap
```

The Gap Agent (Claude Opus 4.7) classifies each KSI as implemented, partial, not_implemented, not_applicable, or evidence_layer_inapplicable (the latter for KSIs with no plausible IaC-evidenceable surface — e.g., procedural KSIs like FedRAMP Security Inbox; SPEC-57.1), given the evidence collected. Underlying 800-53 control status is shown alongside. Requires `ANTHROPIC_API_KEY`. Writes a self-contained HTML report to `.efterlev/reports/gap-<timestamp>.html` and prints the per-KSI summary to the terminal. Every classification is persisted as a Claim record in the provenance store.

### Draft attestation narratives

```bash
efterlev agent document                     # all classified KSIs
efterlev agent document --ksi KSI-SVC-SNT   # one KSI
```

The Documentation Agent (Claude Sonnet 4.6 by default — see [DECISIONS.md](./DECISIONS.md) for the per-agent model-selection rationale) drafts an attestation narrative per classified KSI, grounded in the evidence the Gap Agent cited. Every narrative cites evidence by ID, names what the scanner proved and what it did not. Output is `.efterlev/reports/documentation-<timestamp>.html` with one card per KSI plus an FRMR-compatible `.efterlev/reports/attestation-<timestamp>.json` artifact for 3PAO ingestion and downstream tooling. Cost is typically ~$1-2 for a full baseline; at ~$0.02 per KSI narrative.

### Propose remediation

```bash
efterlev agent remediate --ksi KSI-SVC-SNT
```

The Remediation Agent (Claude Opus 4.7) proposes a `git apply`-ready Terraform diff that closes the gap for one KSI, reading the `.tf` files the evidence referenced. Output is `.efterlev/reports/remediation-<ksi>-<timestamp>.html` with the diff in a monospace block, the explanation of what it changes and what it does NOT cover, and step-by-step "how to apply" guidance. Efterlev never modifies your code; a human reviews the diff and decides.

### Draft a POA&M

```bash
efterlev poam                               # every open KSI
efterlev poam --output poam.md              # write to a specific path
```

Emits a Plan of Action & Milestones markdown for every KSI the Gap Agent classified as `partial` or `not_implemented`. Deterministic — no LLM call. Severity is heuristically derived (not_implemented → HIGH, partial → MEDIUM); reviewer fields (milestones, resources, scheduled completion) are explicit `DRAFT` placeholders the human owner fills in. POA&M IDs derive from the underlying Claim record_id so the document is provenance-linked. OSCAL-shaped POA&M JSON is a v1.5+ deliverable, gated on first OSCAL-Hub-consuming customer.

### Walk the provenance

```bash
efterlev provenance show <record_id>
```

Every generated claim traces back through the reasoning step, the evidence records cited, to the Terraform file and line that produced the evidence. Record IDs are printed by every command for exactly this purpose.

### Review redacted secrets

```bash
efterlev redaction review                   # all scans
efterlev redaction review --scan <scan_id>  # one scan
```

Every LLM prompt Efterlev sends is unconditionally scrubbed for secret-shaped substrings (AWS access keys, GCP API keys, GitHub tokens, Slack tokens, Stripe keys, PEM private keys, JWTs). A per-scan audit log at `.efterlev/redactions/<scan_id>.jsonl` (mode `0o600`) records each redaction's family, a truncated preview, and the record it came from. `efterlev redaction review` renders that log so you can audit what Efterlev did and did not send upstream. The scrubber is conservative and may over-redact; false positives are the safe failure mode.

### Wire it into CI

A drop-in GitHub Action at `.github/workflows/pr-compliance-scan.yml` runs the scanner on every PR, posts a sticky markdown comment with findings + detector coverage, and uploads the `.efterlev/` store as a workflow artifact. The Gap Agent step is opt-in (requires `ANTHROPIC_API_KEY`). See [docs/ci-integration.md](./docs/ci-integration.md) for the full setup, including the `--fail-on-finding` flag for orgs that want CI to gate on any finding.

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

> **Note on SC-28 (encryption at rest).** FRMR 0.9.43-beta does not list SC-28 in any KSI's `controls` array. Per [DECISIONS 2026-04-21 design call #1](./DECISIONS.md) — and re-confirmed in the [2026-04-27 honesty pass](./docs/v1-readiness-plan.md) — the five SC-28 detectors (`encryption_s3_at_rest`, `encryption_ebs`, `rds_encryption_at_rest`, `sqs_queue_encryption`, `sns_topic_encryption`) declare `ksis=[]` rather than shoehorning SC-28 into a thematically-adjacent KSI. We considered KSI-SVC-VRI (integrity via crypto), KSI-SVC-PRR ("Preventing Residual Risk"), and KSI-SVC-RUD ("Removing Unwanted Data"), but rejected each: SC-28 is specifically about confidentiality at rest, while VRI's controls center on SC-13 (integrity), PRR's only control is SC-4 (Information in Shared System Resources), and RUD's controls are SI-12.3 / SI-18.4 (data integrity). The evidence still surfaces in the gap report's **Unmapped findings** section, honest about the current FRMR mapping gap. The 2026-04-27 honesty pass revisited this and confirmed the SC-28 gap is upstream in FRMR 0.9.43-beta, not an Efterlev mapping mistake; tracked as a v0.1.x followup to file an upstream issue with a proposed mapping. **By contrast, the 2026-04-27 honesty pass DID rehome `kms_key_rotation`** from `ksis=[]` to KSI-SVC-ASM ("Automating Secret Management"), whose statement explicitly names "rotation of digital keys" — a mapping the original conservative read missed.

> **Note on KSI-IAM-MFA.** The indicator requires *phishing-resistant* MFA. Our detector evidences that MFA is enforced via IAM policy condition keys (`aws:MultiFactorAuthPresent`), which is MFA presence but not phishing resistance. The phishing-resistance layer lives in IdP configuration (Okta, Entra, Cognito) and is procedural — outside what a scanner can see. The detector README and every per-KSI narrative calls this out explicitly.

> **Note on policy documents built with `jsonencode`.** `python-hcl2` renders `jsonencode({...})` and `data.aws_iam_policy_document.X.json` as `${...}` placeholders rather than resolved JSON. The MFA detector flags these as `mfa_required=unparseable`; the Gap Agent classifies such cases as `partial` with the honest "cannot confirm or refute" narrative rather than a false positive.

Every detector's `README.md` inside `src/efterlev/detectors/` names what it proves and what it does not prove. Read those before trusting a finding.

### On the roadmap

Expansion happens along two axes in parallel: **input sources** (what Efterlev can scan) and **KSI / control coverage** (what it can find). Source-type expansion matters more for adoption; coverage expansion matters more for depth.

- **Shipped (2026-04):** Terraform Plan JSON scan mode (`--plan`); POA&M markdown generator (`efterlev poam`); drop-in GitHub Action for PR compliance checks (`.github/workflows/pr-compliance-scan.yml`); unconditional LLM-prompt secret redaction (7 families) with per-scan audit log; Anthropic retry + Opus→Sonnet fallback.
- **Next:** +16 detectors toward the 30-detector Phase 6 target (IAM, CMT, MLA, SVC themes); OpenTofu declared as first-class alongside Terraform
- **Shipped (2026-04-24):** AWS Bedrock LLM backend for FedRAMP-authorized deployments (GovCloud + commercial). Opt-in via `[bedrock]` extra; container image bakes it in.
- **Mid-term:** CloudFormation and AWS CDK support (CDK compiles to CloudFormation; one parser covers both); Kubernetes manifests + Helm; Pulumi support
- **Later:** CMMC 2.0 overlay; Drift Agent (watches a repo over time, flags regressions in evidenced KSIs); OSCAL-shaped output generators (SSP, AR, POA&M JSON) for Rev5-transition submissions
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

**Current state (2026-04-26): v0 shipped; v1 Phases 1 & 2, Plan JSON mode, prompt hardening, POA&M generator, and the PR GitHub Action landed. All eight pre-launch readiness gates closed at the spec level (A1 identity → A8 launch rehearsal); destination-repo operational setup complete and the release pipeline validated via 5 rc-tag dry-runs (5 real bugs found + fixed). Repository pre-launch private; the public Apache-2.0 flip happens once the remaining maintainer-action items (security-review §8 sign-off, 24-hour fresh-eyes pause, optional GovCloud walkthrough) complete and the maintainer pushes `v0.1.0`.**

### What v0 contains

**Pipeline.** `init → scan → agent gap → agent document → agent remediate → provenance show` runs end-to-end. Every CLI verb is also an MCP tool.

**Detectors (30).** Six v0 + Phase 6-lite six + dogfood-followup two (all 2026-04-22) + A4 detector-breadth sixteen (2026-04-24 → 2026-04-25):
`aws.encryption_s3_at_rest`, `aws.tls_on_lb_listeners`, `aws.fips_ssl_policies_on_lb_listeners`,
`aws.mfa_required_on_iam_policies`, `aws.cloudtrail_audit_logging`, `aws.backup_retention_configured`,
`aws.s3_public_access_block`, `aws.rds_encryption_at_rest`, `aws.kms_key_rotation`,
`aws.cloudtrail_log_file_validation`, `aws.vpc_flow_logs_enabled`, `aws.iam_password_policy`,
`aws.encryption_ebs`, `aws.iam_user_access_keys`,
`aws.security_group_open_ingress`, `aws.rds_public_accessibility`, `aws.s3_bucket_public_acl`, `aws.nacl_open_egress`,
`aws.cloudwatch_alarms_critical`, `aws.guardduty_enabled`, `aws.config_enabled`, `aws.access_analyzer_enabled`,
`aws.kms_customer_managed_keys`, `aws.secrets_manager_rotation`, `aws.sns_topic_encryption`, `aws.sqs_queue_encryption`,
`aws.iam_inline_policies_audit`, `aws.iam_admin_policy_usage`, `aws.iam_service_account_keys_age`, `aws.elb_access_logs`.
All self-contained under `src/efterlev/detectors/aws/<capability>/` with detector.py, mapping.yaml, evidence.yaml,
fixtures/ (including .plan.json equivalence fixtures), and README.md. Each detector's README names what it proves
and what it does not.

**Detector breakdown — 43 total = 36 KSI-mapped + 7 supplementary 800-53-only.**
- **36 KSI-mapped detectors** evidence FRMR-Moderate KSIs directly. Together they cover **30 of 60 KSIs** at
  the infrastructure layer, spanning **8 of 11 themes** (CNA, CMT, IAM, MLA, PIY, RPL, SCR, SVC). The remaining
  three themes (AFR, CED, INR) are entirely procedural/governance and require Evidence Manifests rather than
  detector evidence. See Priority 1 of `docs/v1-readiness-plan.md` for the planned breadth expansion to
  ≥30 KSIs.
- Detector sources: **39 from `terraform`** (read `.tf` files or `terraform show -json` output) +
  **4 from `github-workflows`** (read `.github/workflows/*.yml` for CI/CD, supply-chain-monitoring,
  and supply-chain-mitigation KSIs that have no IaC analog).
- **7 supplementary 800-53-only detectors** carry `ksis=[]` because their underlying control (SC-28 for
  encryption-at-rest families; IA-5 for password policy; AC-3 for S3 public-access blocks) is not listed in
  any KSI's `controls` array in FRMR 0.9.43-beta. Their evidence surfaces in the gap report's "Unmapped
  findings" section — honest about the current FRMR mapping gap, not invented KSI attribution. SC-28
  specifically is the largest gap (5 of the 7 detectors) and is being raised upstream to the FRMR project.
  See "Note on SC-28" below for the full rationale.

**Agents (3).** Gap (Opus 4.7), Documentation (Sonnet 4.6), Remediation (Opus 4.7). Each has its system prompt in a sibling `.md` file — see `src/efterlev/agents/*_prompt.md`. Prompts include explicit per-run-nonced-fence rules and cite-by-fenced-id discipline (see Phase 2 post-review fixup F below).

**Provenance.** SQLite index + content-addressed blob store + append-only JSONL receipt log under `.efterlev/`. Every record (Evidence, Claim, ProvenanceRecord) is content-addressed by SHA-256. `efterlev provenance show <record_id>` walks the chain.

**Output surface.** Self-contained HTML reports under `.efterlev/reports/`: gap-\<ts\>.html, documentation-\<ts\>.html, remediation-\<ksi\>-\<ts\>.html. Inline CSS, no JavaScript, no external fonts — portable, emailable, archivable. Evidence records render with a green left border; Claims render amber with the DRAFT banner. Manifest-sourced citations carry an "attestation" badge to distinguish human-signed from scanner-derived evidence.

**MCP server.** stdio transport, stateless, self-logging. Seven tools covering every CLI verb. Every tool invocation writes one `mcp_tool_call` claim record into the target repo's provenance store before dispatching. See [THREAT_MODEL.md](./THREAT_MODEL.md) T6.

### What v1 Phase 1 added (2026-04-22, commits `d43a2a3` + `7cc86d6`)

**Evidence Manifests** — customer-authored procedural attestations under `.efterlev/manifests/*.yml`. Each YAML binds to one KSI and contains one or more human-signed attestation entries (`statement`, `attested_by`, `attested_at`, `reviewed_at`, `next_review`, `supporting_docs`). At scan time, manifests become `Evidence` records with `detector_id="manifest"` and flow through the Gap Agent alongside detector Evidence. The single highest-leverage addition in v1: the scanner-only ceiling is ~20% of the Moderate baseline; manifests lift coverage toward the procedural-heavy 80%. Full design call in `DECISIONS.md` 2026-04-22 "Phase 1: Evidence Manifests."

**New primitive:** `load_evidence_manifests` in the `evidence/` capability slot (the first primitive there). Deterministic. One provenance record per attestation.

**Renderer badge:** Documentation Report (now carried by Gap Report and Remediation Report too per fixup E) marks manifest-sourced citations with an amber "attestation" pill.

### What v1 Phase 2 added (2026-04-22, commit `5d35bf7`)

**FRMR attestation generator** — `generate_frmr_attestation` primitive serializes `AttestationDraft` records to a typed `AttestationArtifact` and a canonical JSON string. Deterministic (no LLM call inside — the LLM work happened upstream in the Documentation Agent). Output shape is FRMR-inspired (top-level `info` + `KSI`-by-theme nesting + `provenance` block); it is NOT a valid FRMR *catalog* document, because FedRAMP has not published an attestation-output schema and our artifact carries attestation data the catalog schema does not express. Pydantic `extra="forbid"` + `Literal[True]` on `requires_review` is the v1 structural guarantee.

**CLI integration:** `efterlev agent document` now emits `.efterlev/reports/attestation-<ts>.json` alongside the existing HTML report. Single run, two artifacts — human-readable HTML for review, machine-readable JSON for 3PAO ingestion and downstream tooling.

Full design call in `DECISIONS.md` 2026-04-22 "Phase 2: FRMR attestation generator."

### What post-review fixups A–F tightened (2026-04-22, commits `e62e309` → `fcaf94a`)

- **A:** Specific `pydantic.ValidationError` catch in the attestation primitive; dedup `skipped_unknown_ksi` at primitive boundaries; hard-error on missing FRMR cache in `scan`; consolidated ProvenanceStore context in `agent document`; CLAUDE.md schema-posture refresh.
- **B:** `docs/dual_horizon_plan.md` §3.1 rewrite to match the v1 lock.
- **C:** Remediation Agent filters `detector_id="manifest"` Evidence out of source-file assembly; clean short-circuit on manifest-only KSIs.
- **D:** `Evidence.source_ref.file` is repo-relative, not absolute. No user filesystem layout leaks into the provenance store, HTML, or FRMR JSON.
- **E:** Gap Report + Remediation Report now carry the manifest attestation badge when passed `evidence=`. CSS consolidated in the shared stylesheet.
- **F:** Per-run fence nonce (`<evidence_NONCE id="...">` / `<source_file_NONCE path="...">`) hardens the prompt-injection defense against content-injected forged fences. All three agents pass a fresh nonce from `new_fence_nonce()` to every format/parse call in a `run()`. Adversarial test locks in that content-embedded fake fences with mismatching nonces are rejected.

### What external-review honesty pass + hardening added (2026-04-22, subsequent commits)

Four interlocking tranches landed after an external-review pass flagged docs-vs-code discipline gaps. Each carries a DECISIONS entry with rejected alternatives.

- **Secret redaction (`src/efterlev/llm/scrubber.py`).** Regex pattern library for 7 secret families, `scrub_llm_prompt()` called unconditionally by the shared evidence and source-file fence formatters, a `RedactionLedger` contextvar threaded through every agent run, and `.efterlev/redactions/<scan_id>.jsonl` written at mode `0o600` via `os.open`. Auditable via `efterlev redaction review`.
- **Retry + fallback (`src/efterlev/llm/anthropic_client.py`).** Classifier for retryable vs non-retryable Anthropic errors; exponential backoff with full jitter (1s → 60s cap); three attempts on primary then one fallback to `claude-sonnet-4-6`. Injectable sleeper for deterministic tests.
- **POA&M markdown generator (`src/efterlev/primitives/generate/generate_poam_markdown.py`).** Deterministic — severity heuristic only, no LLM. POA&M IDs derive from the Claim `record_id` prefix so the document is provenance-linked. CLI at `efterlev poam`. OSCAL-shaped JSON POA&M remains a v1.5+ deliverable gated on first OSCAL-consuming customer.
- **GitHub Action + CI summary script.** `.github/workflows/pr-compliance-scan.yml` runs scan + optional Gap Agent and posts a sticky PR comment via `scripts/ci_pr_summary.py`, which reads `.efterlev/store.db` + the content-addressed blob store directly through `sqlite3` (no Efterlev package import required, so the CI-shell Python need not share a venv with the Efterlev install). Consumer docs at [docs/ci-integration.md](./docs/ci-integration.md).
- **Store-level `validate_claim_provenance`.** Defense-in-depth: `ProvenanceStore.write_record` rejects a Claim whose `derived_from` cites ids that resolve neither as `ProvenanceRecord.record_id` nor as `Evidence.evidence_id` in a stored evidence payload. Dual-keyed lookup so both calling conventions work; the full unify-on-record_id refactor is deferred.

### Current stable surface

Designed to not break once the repo flips public (per the 2026-04-23 open-source-first posture):

- `@detector` and `@primitive` decorator contracts
- Evidence / Claim / ProvenanceRecord / AttestationDraft / AttestationArtifact / EvidenceManifest / PoamClassificationInput Pydantic models
- CLI verb names and argument shapes (including `poam` and `redaction review`)
- MCP tool names and JSON Schemas
- `.efterlev/` on-disk layout — carved-out: `.efterlev/manifests/` is customer-authored and committed; `.efterlev/redactions/` is audit log at mode `0o600`; rest is tool state and gitignored
- FRMR attestation JSON top-level shape (`info`, `KSI`, `provenance`)
- POA&M markdown section ordering and per-item heading shape

### Changing surface

- Detector content (as more land — Phase 6 target is 30 total; held pending customer signal)
- Agent system prompts (as they're tuned against real LLM output)
- OSCAL generators (deferred to v1.5+, gated on customer pull)

### Tests

930 passing. `ruff check` + `ruff format --check` + `mypy --strict` clean across 164 source files. Unit tests use `StubLLMClient`; full pipeline is verified end-to-end against real Opus 4.7 + Sonnet 4.6 by `scripts/e2e_smoke.py` (requires `ANTHROPIC_API_KEY` for the anthropic backend or `EFTERLEV_BEDROCK_SMOKE=1` + AWS creds for the bedrock backend), with pytest wrappers at `tests/test_e2e_smoke.py` and `tests/test_e2e_smoke_bedrock.py` that skip when the keys are unset. Plan-JSON mode equivalence tests (one per detector) lock in that HCL-mode and plan-mode produce identical evidence for the same configuration.

### What's NOT in scope right now (per v1 lock)

- **OSCAL-shaped SSP / AR / POA&M JSON generators.** A reviewer-ready POA&M markdown ships today via `efterlev poam`; the OSCAL-shaped JSON form is v1.5+, gated on first Rev5-transition or OSCAL-Hub-consuming customer.
- ~~**AWS Bedrock backend** (commercial + GovCloud). v1 Phase 3, pulled on GovCloud prospect demand.~~ **Shipped 2026-04-24** as pre-launch readiness gate A3 — see SPEC-10.
- **Non-Terraform input sources** (CloudFormation, CDK, Pulumi, Kubernetes manifests, runtime cloud APIs). v1.5+.
- **CMMC 2.0 overlay.** v1.5+ when ICP B becomes primary.
- **Public package on PyPI.** Deferred until repo opens at first customer engagement or Month 6.

---

## Contributing

We want contributors. The detector library is designed to make the common contribution — "here's a new KSI indicator I can evidence from Terraform" — a self-contained folder that doesn't touch the rest of the codebase.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the five-minute path from `git clone` to running tests, and the hour path from idea to open PR. Community conduct is governed by the [Code of Conduct](./CODE_OF_CONDUCT.md) (Contributor Covenant 2.1, with an Efterlev-specific interpretation section).

Good first issues are labeled `good first issue` on GitHub. The most valuable contributions right now are new detectors covering KSIs on the roadmap.

---

## Governance

Benevolent-dictator model today (`@lhassa8`), transitioning to a technical steering committee when the project has 10 contributors with sustained activity (at least one merged PR in each of the prior 3 calendar months, sustained for 6 months). The full model — roles, decision-making, maintainer invitation, SC trigger, and the change process for governance itself — lives in [GOVERNANCE.md](./GOVERNANCE.md). See [CONTRIBUTING.md](./CONTRIBUTING.md) for the contribution path and [DECISIONS.md](./DECISIONS.md) for the architectural-decision log.

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
- [docs/RELEASE.md](./docs/RELEASE.md) — release process, verification contract, and release-notes template
- [docs/deploy-govcloud-ec2.md](./docs/deploy-govcloud-ec2.md) — running Efterlev inside an AWS GovCloud boundary using the Bedrock backend
- [GOVERNANCE.md](./GOVERNANCE.md) — decision-making and maintainer roles
- [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) — Contributor Covenant 2.1 with project-specific interpretation
