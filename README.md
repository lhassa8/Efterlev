# Efterlev

**Compliance scanning for SaaS teams pursuing FedRAMP 20x — that lives in your repo, not a SaaS dashboard.**

Efterlev reads your Terraform, classifies it against the 60 thematic Key Security Indicators, drafts FRMR-compatible attestations grounded in cited source lines, and proposes code-level remediations. Locally. No procurement cycle. No vendor account. Apache 2.0.

```bash
pipx install efterlev
cd path/to/your-terraform
efterlev init
export ANTHROPIC_API_KEY=sk-ant-...
efterlev report run
```

Pronounced "EF-ter-lev." From Swedish *efterlevnad* (compliance).

### Or have an AI assistant do it for you

Paste this into [Claude Code](https://claude.com/claude-code), Cursor, Codex, Kiro, or any other AI assistant with shell access. It'll ask the questions it needs (where your Terraform is, whether your key is exported), pick the right scan mode for your codebase, install Efterlev, run the pipeline, and brief you on the output.

```text
You are helping me run Efterlev (https://efterlev.com) against my Terraform
for the first time. Efterlev is a FedRAMP 20x compliance scanner that reads
Terraform, classifies it against 60 Key Security Indicators, and drafts
FRMR-compatible attestations with cited source lines. It runs locally; the
only outbound call is to the LLM endpoint I configure.

## Step 1 — pick the LLM backend

Ask me which backend I want:

  (a) Direct Anthropic API — fastest setup; needs an ANTHROPIC_API_KEY
      from https://console.anthropic.com.
  (b) AWS Bedrock — if I'm on GovCloud, already have AWS configured, or
      don't want a separate Anthropic account.

Also ask me for the absolute path to my Terraform code.

## Step 2a — Anthropic API path

1. Tell me to grab a key at https://console.anthropic.com/settings/keys
   and `export ANTHROPIC_API_KEY=sk-ant-...` if not already set.
2. Verify: `echo "${ANTHROPIC_API_KEY:0:10}"` should print something
   starting with `sk-ant-`. If empty, stop until I export it.
3. Install or upgrade Efterlev:
   - If `efterlev` isn't on my PATH: `pipx install efterlev` (or
     `brew install pipx` first if pipx is missing).
   - If it is: `pipx upgrade efterlev`.
   - Confirm `efterlev --version` prints `efterlev 0.1.3` or higher.
     If it still shows an older version, do a clean reinstall:
     `pipx uninstall efterlev && pipx install efterlev`.

Then jump to Step 3.

## Step 2b — Bedrock path

1. Ask me which AWS region to use (default `us-east-1` if I have no
   preference). Also confirm `aws sts get-caller-identity --region <region>`
   succeeds. If it fails, stop and tell me to fix `aws configure`.
2. Discover available Anthropic inference profiles in that region:
   `aws bedrock list-inference-profiles --region <region> --type-equals SYSTEM_DEFINED`
   Filter the result down to entries whose `inferenceProfileName` or
   underlying `models[].modelArn` references Anthropic. (System-defined
   profiles are the cross-region inference profiles, prefixed `us.` /
   `eu.` etc. — those are what works for the newer Claude 4.x models.
   On-demand foundation-model IDs like `anthropic.claude-opus-4-7` are
   rejected by Bedrock for these models.)
3. From the filtered list, group by family — Opus / Sonnet / Haiku — and
   pick the **latest** (highest version) of each. Present me with exactly
   three options:
     [O] Latest Opus:    <inferenceProfileName>   (ARN: <inferenceProfileArn>)
     [S] Latest Sonnet:  <inferenceProfileName>   (ARN: <inferenceProfileArn>)
     [H] Latest Haiku:   <inferenceProfileName>   (ARN: <inferenceProfileArn>)
   If a tier has zero available profiles, omit that line and tell me
   which tier is missing (e.g. "no Opus profile enabled in this account
   — request access at console.aws.amazon.com/bedrock"). If ALL three
   tiers are empty, stop — I need to enable Anthropic model access in
   the Bedrock console before continuing.
4. Ask me which tier to use. Default suggestion: Opus (best classification
   quality), Sonnet (~5x cheaper, fine for first runs), Haiku (cheapest,
   for quick smoke tests).
5. Capture the `inferenceProfileArn` (prefer the `us.` / regional ARN over
   any global variant if both are present) and remember it as `MODEL_ARN`.
6. Install or upgrade Efterlev with the Bedrock extra:
   - If not yet installed: `pipx install 'efterlev[bedrock]'` (keep the
     quotes — the bracket extra needs them; or `brew install pipx`
     first if pipx is missing).
   - If installed: `pipx upgrade 'efterlev[bedrock]'`.
   - Confirm `efterlev --version` prints `efterlev 0.1.3` or higher.
     If it still shows an older version, do a clean reinstall:
     `pipx uninstall efterlev && pipx install 'efterlev[bedrock]'`.

## Step 3 — init

`cd` to my Terraform path. Then:

  - Anthropic backend:
      `efterlev init --target .`
  - Bedrock backend:
      `efterlev init --target . --llm-backend=bedrock --llm-region=<region> --llm-model=<MODEL_ARN>`

If `efterlev init` errors with ".efterlev already exists", or if I'm
re-running after an earlier Efterlev version touched this workspace,
re-run with `--force` — it preserves `.efterlev/manifests/` (the
canonical Evidence-Manifest pattern) while regenerating the FRMR cache,
provenance store, and `config.toml`. Re-init is the right move on
upgrade because `config.toml` may have stale model IDs from the old
version (especially on the Bedrock path, where the latest available
inference profiles change across releases).

## Step 4 — doctor + scan

1. `efterlev doctor` — surface any warnings or fails.
2. Pick a scan mode:
   - If `terraform` is available AND my code has `module "..." {}` blocks,
     try plan-JSON: `terraform init && terraform plan -out plan.bin &&
     terraform show -json plan.bin > plan.json`, then
     `efterlev scan --plan plan.json`. If `terraform plan` fails on
     "(known after apply)" errors or a missing/locked S3 backend
     (try `terraform init -backend=false` then `terraform plan
     -refresh=false`), fall back to HCL mode and note which
     module-resolved resources won't surface.
   - Otherwise: `efterlev scan`.

## Step 5 — agents

Run `efterlev agent gap` (~60–90s; ~$0.50–1 on Opus). Tell me the path to
the HTML report and offer to open it.

Ask if I also want narratives (`efterlev agent document`, ~$1–2 on Sonnet)
and POA&M markdown (`efterlev poam`, free, deterministic).

## Constraints

- Don't run `efterlev agent remediate` without me asking — it generates
  code-level diffs and I want to be in the loop.
- Don't modify my Terraform. Don't commit anything.
- Soft cost cap: $3 on the Anthropic path, $5 on the Bedrock path
  (Bedrock retries can burn more on first-run config issues). Stop and
  check back before exceeding.
- If anything fails or surprises you, stop and ask — don't paper over.

## When done

Brief me with:
- Counts of `implemented` / `partial` / `not_implemented` /
  `evidence_layer_inapplicable` KSIs.
- Paths to the gap report, FRMR JSON, and POA&M markdown.
- Anything notable: secrets caught by the redaction layer, KSIs flagged
  for review, modules where evidence was sparse.
```

---

## Why this exists

A 100-person SaaS company just got told by its biggest prospect: *"we'll buy, but only if you're FedRAMP Moderate."*

The team googles it. Consulting engagements start at $250K. SaaS compliance platforms cover SOC 2 beautifully and treat FedRAMP as a footnote. Enterprise GRC tooling is priced for the wrong scale. A NIST document family runs to thousands of pages.

What they actually need is something that reads their Terraform and tells them, in their own language, what's wrong and how to fix it. Something a single engineer can install on a Tuesday and show results at Wednesday's standup. Output concrete enough that their 3PAO can use it; honest enough that the 3PAO won't throw it out.

Efterlev is that tool.

It targets **FedRAMP 20x** — the new authorization track that replaces narrative-heavy System Security Plans with measurable outcomes called **Key Security Indicators**. KSIs are concrete things ("encrypt network traffic," "enforce phishing-resistant MFA") that can be assessed against actual evidence rather than long descriptions of intent. Most new SaaS authorizations starting in 2026 will target this track. Efterlev's primary internal abstraction is the KSI; **FRMR** (the machine-readable format FedRAMP 20x is standardizing on) is the primary output.

---

## What it does

- **Scans** your Terraform — both raw `.tf` files and `terraform show -json` plan output — for evidence of 60 thematic KSIs, backed by underlying NIST 800-53 Rev 5 controls
- **Classifies** each KSI as implemented, partial, not_implemented, not_applicable, or `evidence_layer_inapplicable` (the honest answer for procedural KSIs no scanner can see)
- **Drafts** FRMR-compatible attestation JSON grounded in that evidence — every assertion cites its source line
- **Proposes** code-level remediation diffs you can review, edit, or apply
- **Generates** a reviewer-ready POA&M markdown for every open KSI
- **Traces** every claim back to the file and line that produced it (`efterlev provenance show <id>`)
- **Watches**: `efterlev report run --watch` re-runs the full pipeline on every save (debounced 2s)

Everything runs locally. The only outbound network call is to your configured LLM endpoint — direct Anthropic API by default, or **AWS Bedrock** (`[bedrock]` extra) for FedRAMP-authorized GovCloud deployments. Scanner output is fully deterministic and offline.

## What it doesn't do

- It does not produce an Authorization to Operate. Humans and 3PAOs do that.
- It does not certify compliance. It produces drafts that accelerate the human review cycle.
- It does not guarantee LLM-generated narratives are correct. Every claim carries `requires_review: Literal[True]` at the type level — not a flag, not a string.
- It does not cover SOC 2, ISO 27001, HIPAA, or GDPR. Other tools serve those well.
- It does not scan live cloud infrastructure (yet — v1.5+).
- It does not replace AWS Config / Security Hub for runtime evaluation. Efterlev is the pre-deploy IaC layer; AWS-native is the runtime evidence layer. See [docs/aws-coexistence.md](./docs/aws-coexistence.md).

For the honest full accounting, see [LIMITATIONS.md](./LIMITATIONS.md).

---

## How to run it

```bash
efterlev init                                  # creates .efterlev/ workspace
efterlev scan                                  # raw .tf files
# OR for module-composed codebases (the dominant pattern):
terraform init && terraform plan -out plan.bin && terraform show -json plan.bin > plan.json
efterlev scan --plan plan.json                 # ~60% more evidence on real codebases

efterlev agent gap                             # KSI-by-KSI classification (Opus 4.7)
efterlev agent document                        # FRMR JSON + HTML attestations (Sonnet 4.6)
efterlev agent remediate --ksi KSI-SVC-SNT     # Terraform diff that closes the gap (Opus 4.7)
efterlev poam                                  # POA&M markdown for every open KSI
efterlev provenance show <record_id>           # walk any claim back to source
```

Or just:

```bash
efterlev report run                            # full pipeline: init → scan → gap → document → poam
efterlev report run --watch                    # re-run on every file change (2s debounce)
```

Pre-flight check: `efterlev doctor` (Python version, workspace, FRMR cache freshness, API key shape, Bedrock creds — all offline).

Wire it into CI: drop-in GitHub Action at `.github/workflows/pr-compliance-scan.yml` posts a sticky markdown PR comment with findings + detector coverage. See [docs/ci-integration.md](./docs/ci-integration.md). Tutorials for GitLab CI, CircleCI, and Jenkins on the [docs site](https://efterlev.com).

---

## How it's built

Three layers, each with a clear job:

- **Detectors** — small, deterministic Python folders. One detector = one folder = one compliance pattern. No AI. The detector library is the community-contributable surface.
- **Primitives** — typed functions wrapping the things agents need ("scan this directory," "validate this output," "load that catalog"). MCP-exposed.
- **Agents** — focused reasoning loops backed by Claude. Each has its system prompt in a plain `.md` file you can read and audit. AI is used for the parts where reasoning matters; never for the parts where determinism does.

This split — **deterministic for evidence, AI for reasoning, different model weights for different cognitive loads** — is the most important design decision in the project. It's what lets us tell auditors and 3PAOs the truth: scanner findings are verifiable facts about your code; AI claims are drafts you can audit but should not blindly trust.

**Hallucination defenses are structural, not advisory.** Every AI-generated claim links to evidence records via content-addressed IDs. Prompts wrap evidence in `<evidence_NONCE>` XML fences with a per-run nonce; a post-generation validator rejects any output citing IDs the model didn't actually see. The provenance store rejects any claim whose `derived_from` cites IDs that don't resolve. The DRAFT marker is `Literal[True]` at the type level — there's no flag to clear it.

**Secrets never leave the machine unredacted.** Every LLM prompt is unconditionally scrubbed for 7 secret families (AWS keys, GCP keys, GitHub tokens, Slack tokens, Stripe keys, PEM private keys, JWTs). The scrubber has no opt-out path. Each redaction writes an audit line to `.efterlev/redactions/<scan_id>.jsonl` (mode `0o600`); review with `efterlev redaction review`.

**LLM calls degrade predictably.** Transient errors retry with exponential backoff + full jitter (3 attempts). On primary-model exhaustion, falls back once from Opus to Sonnet before surfacing a failure. Non-retryable errors (auth, invalid request) fail immediately.

For deeper architectural detail, see [docs/architecture.md](./docs/architecture.md). For the design history including reversals and tradeoffs, see [DECISIONS.md](./DECISIONS.md).

---

## Coverage at v0.1.3

- **45 detectors** — 38 KSI-mapped + 7 supplementary 800-53-only (where FRMR 0.9.43-beta doesn't yet map the underlying control)
- **31 of 60 thematic KSIs** covered, across **8 of 11 themes** (CNA, CMT, IAM, MLA, PIY, RPL, SCR, SVC). The remaining three themes (AFR, CED, INR) are entirely procedural — covered by customer-authored Evidence Manifests rather than detector evidence.
- **Detector sources:** 41 Terraform + 4 GitHub workflows
- **Three agents:** Gap (Opus 4.7), Documentation (Sonnet 4.6), Remediation (Opus 4.7)
- **Two LLM backends:** Anthropic API (default) + AWS Bedrock (`[bedrock]` extra, GovCloud-deployable)
- **1026 tests passing;** mypy strict + ruff check + ruff format clean across 172 source files

**Coverage relative to FedRAMP 20x Phase 2's 70% automated-validation threshold:** the threshold applies to the customer's whole authorization package, not to any single tool. Efterlev covers 31 KSIs at the IaC layer pre-deploy; AWS-native services (Config, Security Hub, CloudTrail, Inspector, GuardDuty) cover roughly 14 KSIs at the runtime layer. Honest union: ~33 of 63 KSIs (~52%) — distinct layers, not double-counted. Reaching 70% takes both. See [docs/aws-coexistence.md](./docs/aws-coexistence.md) for the strategic mapping and [docs/csx-mapping.md](./docs/csx-mapping.md) for how the outputs map to CSX-SUM / MAS / ORD.

---

## Where Efterlev fits

Sits **alongside AWS Config / Security Hub / CloudTrail**, not in place of them:

| | Efterlev | AWS-native |
|---|---|---|
| **When** | Pre-deploy, on every commit or save | Post-deploy, on a 3-day cadence |
| **Reads** | Terraform `.tf` + `.github/workflows/*.yml` | Live AWS API state, runtime events |
| **Output** | Per-KSI attestation JSON + POA&M markdown | Config evaluations, Security Hub findings, CloudTrail logs |
| **Cost** | Free (Apache 2.0, runs locally) | AWS spend |

A FedRAMP 20x customer pursuing the 70% automated threshold typically wires both, plus procedural Evidence Manifests under `.efterlev/manifests/*.yml` for the procedural-only themes detectors can't see.

---

## Run it from another AI session

```bash
efterlev mcp serve
```

Exposes every CLI verb as an MCP tool over stdio. Point Claude Code (or any MCP client) at it and drive scans, agent calls, and provenance walks from another AI session. Our own agents use the same MCP interface — that's how we know it works. If you want to build a compliance workflow Efterlev doesn't ship, write your own agent against the MCP surface; you don't need to fork the codebase.

---

## Documentation

Full docs site: **[efterlev.com](https://efterlev.com)** — quickstart, concepts, tutorials (CI integration, GovCloud deployment, writing detectors, customizing agent prompts), CLI reference, and comparisons against Paramify, Comp AI, Vanta/Drata, and traditional consulting.

In this repo:
- [`docs/architecture.md`](./docs/architecture.md) — three-layer architecture in depth
- [`docs/aws-coexistence.md`](./docs/aws-coexistence.md) — how Efterlev fits next to AWS-native services
- [`docs/ci-integration.md`](./docs/ci-integration.md) — drop-in GitHub Action for PR compliance scans
- [`docs/csx-mapping.md`](./docs/csx-mapping.md) — outputs mapped to CSX-SUM / MAS / ORD
- [`docs/deploy-govcloud-ec2.md`](./docs/deploy-govcloud-ec2.md) — running inside an AWS GovCloud boundary
- [`docs/icp.md`](./docs/icp.md) — Ideal Customer Profile; the lens for every product decision
- [`docs/dual_horizon_plan.md`](./docs/dual_horizon_plan.md) — roadmap beyond v0.1.0
- [`CHANGELOG.md`](./CHANGELOG.md) — release-by-release record

---

## Contributing

We want contributors. The detector library is designed to make the common contribution — "here's a new KSI indicator I can evidence from Terraform" — a self-contained folder that doesn't touch the rest of the codebase.

[`CONTRIBUTING.md`](./CONTRIBUTING.md) has the five-minute path from `git clone` to running tests, and the hour path from idea to open PR. Community conduct: [Contributor Covenant 2.1](./CODE_OF_CONDUCT.md). Good first issues are labeled `good first issue` on GitHub. The most valuable contributions right now are new detectors covering KSIs on the roadmap.

---

## Status, governance, license

**Status:** v0.1.3 is current. See [CHANGELOG.md](./CHANGELOG.md) for per-release notes (v0.1.0 first public on 2026-04-29; four patch releases since, all addressing real-world first-run issues caught by deep-dive shakedowns). Verify a published artifact with `bash scripts/verify-release.sh v0.1.3` (PEP 740 PyPI attestations + cosign keyless OIDC + SLSA provenance on `ghcr.io/efterlev/efterlev`).

**Governance:** Benevolent-dictator model today (`@lhassa8`), transitioning to a technical steering committee at 10 sustained-activity contributors. Full model in [GOVERNANCE.md](./GOVERNANCE.md). Architectural decisions: [DECISIONS.md](./DECISIONS.md). The project may eventually be donated to a neutral foundation (OpenSSF / Linux Foundation / CNCF) if contributor diversity warrants — that decision is not made and not time-boxed.

**License:** Apache 2.0. See [LICENSE](./LICENSE).

**Security:** Coordinated disclosure process in [SECURITY.md](./SECURITY.md). Threat model for Efterlev itself: [THREAT_MODEL.md](./THREAT_MODEL.md). The pre-launch security review (signed by the maintainer) is at [docs/security-review-2026-04.md](./docs/security-review-2026-04.md).

---

## Credits

Efterlev was bootstrapped in a 4-day hackathon using [Claude Code](https://claude.com/claude-code). The architecture commits to keeping Claude Code (and other MCP-capable agents) as first-class integration partners — that's what "agent-first" means here, structurally, not as marketing.

Built on [compliance-trestle](https://github.com/IBM/compliance-trestle) for OSCAL catalog loading, on the [FedRAMP Machine-Readable (FRMR) catalog](https://github.com/FedRAMP/docs), and on the [NIST SP 800-53 Rev 5 catalog](https://github.com/usnistgov/oscal-content). Those projects make this one possible.
