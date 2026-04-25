# FAQ

Hard questions named explicitly. If yours isn't here, [open a Discussion](https://github.com/efterlev/efterlev/discussions) or file a [docs issue](https://github.com/efterlev/efterlev/issues/new/choose).

## Why another compliance tool?

Because the existing ones don't fit a SaaS company starting its first FedRAMP Moderate authorization in 2026.

- Vanta, Drata, Secureframe — SaaS dashboards that nail SOC 2 and have FedRAMP as a footnote.
- Comp AI — open source, but multi-framework with FedRAMP at ~41% coverage in their own demo.
- Paramify — FedRAMP-specialist GRC tool, $145–180K/year, sits in the budget category our ICP doesn't yet have.
- compliance.tf — Terraform-compliance enforcement at module-download time. Excellent for greenfield infra; mismatched for an existing codebase.
- A consultant — $250K starting line, 12–18 month delivery cadence pre-20x.

Efterlev fills the niche for a 50–200 engineer SaaS where a DevSecOps lead owns the FedRAMP push and the budget hasn't caught up yet. Free to install, scans your existing Terraform, runs locally, no vendor lock-in.

[Detailed comparisons](comparisons/paramify.md)

## Will this ever go closed-source?

No. The pure-OSS posture is locked in [`DECISIONS.md` 2026-04-23](https://github.com/efterlev/efterlev/blob/main/DECISIONS.md): no commercial tier, no paid layer, no managed SaaS. If sustainability becomes untenable, we enter maintenance mode or seek a foundation home (OpenSSF / LF / CNCF). Monetization is not introduced by stealth.

## Why FRMR-first instead of OSCAL?

FRMR (FedRAMP Machine-Readable) is the format FedRAMP 20x is standardizing on. New SaaS authorizations in 2026 target 20x; OSCAL was the right answer for the legacy Rev 5 path. Both can be true.

For users transitioning Rev 5 submissions or feeding RegScale's OSCAL Hub, OSCAL output is on the v1.5+ roadmap. Pulled forward when a Rev5-transition customer surfaces. The architecture's `oscal/` generator slot is reserved.

## Can I use Efterlev for SOC 2 / ISO 27001 / HIPAA?

No. Efterlev is FedRAMP and DoD IL-focused. Other frameworks have well-established tooling — Comp AI and Vanta cover SOC 2 / ISO 27001 / HIPAA / GDPR comprehensively. Efterlev's value is depth in gov-grade frameworks, not breadth across every compliance acronym.

The architecture doesn't *prevent* a SOC 2 detector pack — the `@detector` decorator and KSI-mapping discipline are framework-agnostic — but adding one isn't on the roadmap. If you fork Efterlev for a SOC 2 derivative, you're a separate project; we're happy to be neighbors.

## What happens if my 3PAO rejects an Efterlev-drafted attestation?

That's the system working as designed. Efterlev produces drafts; humans (your team, your consultant, your 3PAO) review and revise them. Every LLM-generated artifact carries a `DRAFT — requires human review` marker that's not removable by configuration — it's a `Literal[True]` at the type level.

The provenance chain (every claim traces back to specific evidence records and the Terraform line that produced them) is the defensible answer when a 3PAO challenges a claim. If they dispute a specific assertion, walking the chain shows exactly what the scanner saw — and exactly what the human who reviewed the draft chose to keep, edit, or remove.

## Does Efterlev send my Terraform to anyone?

The scanner doesn't. It runs locally, reading `.tf` files via `python-hcl2` (or via `terraform show -json` plan files in CI mode). Findings land in a local SQLite store under `.efterlev/`.

The agents (Gap, Documentation, Remediation) call an LLM endpoint for reasoning. By default that's the Anthropic API direct; configured for Bedrock, traffic goes to AWS Bedrock instead — including AWS GovCloud Bedrock for FedRAMP-authorized boundaries.

Before any prompt leaves your machine:

- Secrets matching seven structural patterns (AWS access keys, GCP API keys, GitHub tokens, Slack tokens, Stripe keys, PEM private keys, JWTs) are scrubbed by `scrub_llm_prompt`. Replaced with `[REDACTED:family:sha256-prefix]` placeholders.
- The redaction event is logged to `.efterlev/redactions/<scan-id>.jsonl` so you can audit what was scrubbed and what wasn't.

The scrubber is unconditional and not behind a feature flag. The failure mode is over-redaction (false positives), not silent leakage. Read [`THREAT_MODEL.md`](https://github.com/efterlev/efterlev/blob/main/THREAT_MODEL.md) for the full posture.

## What if my code is in something other than Terraform?

v0.1.0 supports Terraform and OpenTofu only — these share syntax and the same `python-hcl2` parser handles both. CloudFormation, AWS CDK, Pulumi, and Kubernetes manifests are roadmap items pulled forward by customer demand.

The detector contract is source-typed (`source="terraform"`), so adding a new source family is a matter of writing the parser plus parallel detectors — not rearchitecting. If you have a non-Terraform-primary stack and want Efterlev to scan it, file a Discussion describing the use case.

## Is Efterlev FedRAMP-authorized itself?

No. Efterlev is a developer tool that runs locally or in CI. It's not an authorized cloud service. Using Efterlev does not confer any authorization status on your system.

The Bedrock backend lets you run Efterlev *inside* a FedRAMP-authorized AWS GovCloud boundary — the inference traffic stays in GovCloud — but that's about the deployment of Efterlev, not about Efterlev itself being a FedRAMP CSO.

## Why is the Gap Agent so much more expensive than the Documentation Agent?

Different model selection per agent, tuned to the cognitive load.

- **Gap Agent → Claude Opus 4.7.** Classifying ambiguous evidence requires judgment calls and the discipline to refuse to borrow evidence from unrelated KSIs. Cheaper models drift on the honesty posture.
- **Documentation Agent → Claude Sonnet 4.6.** Structured extractive writing against a strict format contract. Sonnet handles it at roughly 1/5 the cost-per-token with no observed quality delta in reference CI runs.
- **Remediation Agent → Claude Opus 4.7.** Generating syntactically valid Terraform diffs grounded in real source — code generation plus architectural judgment. Opus-grade.

Each agent's `model` argument is overridable per call. The framework is built to swap in AWS Bedrock as a backend without touching agent code. [Read the design call](https://github.com/efterlev/efterlev/blob/main/DECISIONS.md).

## Can I use a local LLM (Ollama, vLLM) instead of Anthropic / Bedrock?

Not at v0.1.0. The detector library is deterministic and offline; the agents call Claude. Local-LLM support would mean writing a third backend (alongside `AnthropicClient` and `AnthropicBedrockClient`); the contract is `LLMClient` and the path is open. No PRs blocked on architecture; just nobody's done it yet.

This matters for fully-air-gapped GovCloud boundaries. If you're in that situation, file a Discussion — your use case helps prioritize.

## Why does running Efterlev cost money?

The scanner is free and runs offline. The LLM agents call Anthropic or Bedrock, which charge per token.

Rough budget for a 60-KSI Gap classification on a real codebase:

- Anthropic-direct: ~$1–2 per full-baseline run, depending on evidence density.
- Bedrock commercial: comparable order of magnitude; pricing differs per region.
- Bedrock GovCloud: noticeably higher per-token rate. Your finance team should know before approving the deploy.

The `efterlev redaction review` CLI shows what was sent in each prompt; the provenance store records token counts and request IDs.

## I found a security issue. Where do I report it?

[`SECURITY.md`](https://github.com/efterlev/efterlev/blob/main/SECURITY.md). Use GitHub Security Advisories (preferred) or `security@efterlev.com`. Acknowledgment within 3 business days; 90-day default coordinated-disclosure window. **Do not** file as a public issue.

## How do I contribute?

[`CONTRIBUTING.md`](https://github.com/efterlev/efterlev/blob/main/CONTRIBUTING.md). The most-welcomed contribution shape is a new detector — self-contained folder, well-defined contract, low coupling to the rest of the codebase. The [Write your first detector tutorial](tutorials/write-a-detector.md) is the path from "I have an idea" to "PR opened."

## Can I see what an Efterlev scan looks like before installing?

Yes — [`govnotes-demo`](https://github.com/efterlev/govnotes-demo) is the canonical demo repo with a CI workflow that runs Efterlev on every PR. The `.efterlev/reports/` artifacts are uploaded as workflow artifacts; download one to see real HTML output, or look at the sticky PR comment on any open PR.
