# SPEC-12: GovCloud deploy tutorial

**Status:** tutorial landed 2026-04-24; end-to-end maintainer walkthrough on a real GovCloud EC2 instance is the remaining acceptance check
**Gate:** A3
**Depends on:** SPEC-10 (AnthropicBedrockClient — implemented), SPEC-11 (region config — implemented), SPEC-13 (smoke test — implemented; serves as the tutorial's automated acceptance check)
**Blocks:** A6 SPEC-44 (docs-site version of this tutorial refines into a polished page at launch)
**Size:** S

## Goal

A pre-launch-ready markdown tutorial that walks a DevSecOps engineer from "empty EC2 instance inside our GovCloud boundary" to "working `efterlev agent gap` run using Bedrock," with no internet egress to `anthropic.com` at any point. This is the load-bearing proof point that Efterlev runs where customers need it to run.

## Scope

- Markdown tutorial at `docs/deploy-govcloud-ec2.md` (pre-A6-docs-site location; SPEC-44 later moves and polishes it onto the docs site).
- Audience: DevSecOps engineer or platform engineer who already has a FedRAMP-authorized AWS GovCloud AWS boundary.
- Covers: IAM policy, VPC endpoint for Bedrock, EC2 instance setup, Efterlev install via container (air-gap-viable), no-egress verification steps, troubleshooting.
- Cost-profile callout: Bedrock pricing differs from Anthropic-direct; named explicitly.

## Non-goals

- Teaching FedRAMP itself or explaining why an engineer would want GovCloud. Readers arriving at this page already know that.
- Non-AWS GovCloud deployment (Azure Government, GCP IL5). Separate specs if customer-pulled.
- Fully air-gapped (no internet at all) beyond "no egress to `anthropic.com`." True air-gap is v1.5+ (needs a local LLM backend, not in scope for A3).
- Terraform for the deployment itself. The tutorial uses AWS Console + CLI commands; a Terraform module is a post-launch follow-up if demand surfaces.
- Pulumi / CDK equivalents. Same reasoning.

## Interface (content outline)

`docs/deploy-govcloud-ec2.md` sections, in order:

1. **When to use this deployment.** Two sentences: you have a GovCloud boundary + a FedRAMP 20x authorization effort in flight; you want Efterlev running inside that boundary so no evidence metadata crosses it.

2. **What Efterlev does not phone home.** Scanner is fully local. The only outbound call is the LLM inference for the three agents; using Bedrock keeps that inside AWS.

3. **Prerequisites.**
   - An AWS GovCloud account with IAM admin for the setup steps.
   - Amazon Bedrock model access enabled in the target region (us-gov-west-1 or us-gov-east-1). Instructions to request via the Bedrock console.
   - Choice of EC2 instance size — recommend `t3.medium` or `t3.large` for interactive use, `c6i.xlarge` for CI runs with parallelism. No GPU required (Efterlev does no local inference).

4. **Step 1: IAM policy.** Copy-pasteable JSON for a least-privilege policy: `bedrock:InvokeModel`, `bedrock:Converse`, scoped to the expected model ARN. Attached to an EC2 instance profile.

5. **Step 2: VPC endpoint for Bedrock.** Creating the `com.amazonaws.us-gov-west-1.bedrock-runtime` interface VPC endpoint so Bedrock traffic never leaves the VPC. Security-group config. DNS considerations.

6. **Step 3: Launch the EC2 instance.** Amazon Linux 2023 recommended. Container or pipx install. Both paths documented.

7. **Step 4: Configure Efterlev.** `efterlev init --llm-backend bedrock --llm-region us-gov-west-1 --llm-model us.anthropic.claude-opus-4-7-v1:0`. Resulting `.efterlev/config.toml` shown.

8. **Step 5: Verify no-egress.** Block egress to `anthropic.com` at the security-group level; run `efterlev agent gap`; confirm it works. This is the test that the boundary is actually being held.

9. **Step 6: Run against your Terraform.** Mount or clone your Terraform, run `scan` + `agent gap` + `agent document`, confirm reports land in `.efterlev/reports/`.

10. **Cost profile.** Bedrock pricing per model ID as of the docs-site build; note that it differs from Anthropic-direct and gives actual per-KSI-run numbers so the engineer's finance team isn't surprised. Keep the numbers as pointers to the AWS pricing page rather than hardcoded (to avoid stale numbers), but show an order-of-magnitude example.

11. **Troubleshooting.** Common failures: `AccessDeniedException` (Bedrock model access not granted), model ID mismatch (commercial ID in GovCloud), VPC endpoint DNS not resolving, IMDS v2 required for instance-profile credentials. Each with resolution.

12. **Further reading.** Links to AWS Bedrock docs, FedRAMP 20x status page, Efterlev's `THREAT_MODEL.md`.

## Behavior

- Tutorial is reproducible: a reader who has the prerequisites can work through each step copy-pasting commands and end up with a working deployment.
- Every copy-pasteable command block is tested by the maintainer during SPEC-13 first dry-run.
- Tutorial explicitly calls out where it stops being "copy-paste this command" and starts being "consult your AWS admin" (e.g., model access request, which is UI-only).

## Data / schema

N/A (pure documentation).

## Test plan

- **Walkthrough review:** a reader other than the author walks through the tutorial against a throwaway EC2 instance; surfaces any copy-paste errors, missing commands, or unclear steps.
- **Reproducibility:** steps 1–7 land the target state on first attempt without improvisation.
- **No-egress test:** the step-5 verification actually blocks egress to `anthropic.com` and confirms the run works. Reviewer attests.
- **Link validation:** every external link resolves at review time and at docs-site build time.

## Exit criterion

### Tutorial landed 2026-04-24

- [x] `docs/deploy-govcloud-ec2.md` exists with all 12 sections in the planned order. Reproducibility note up top is honest about the not-yet-walked-end-to-end status.
- [x] Section 1 — when-to-use scoping (and when to *not* use this — small SaaS without GovCloud should run from laptop / commercial CI instead).
- [x] Section 2 — Efterlev's no-phone-home commitments named explicitly, with secret-redaction pointer to THREAT_MODEL.md.
- [x] Section 3 — prerequisites: GovCloud account + Bedrock model access + IAM admin + EC2 sizing guidance.
- [x] Section 4 — IAM policy with a copy-paste JSON. Explicit callout that resource ARNs use the `aws-us-gov` partition (a thing people miss).
- [x] Section 5 — VPC endpoint creation with `--private-dns-enabled` flagged as load-bearing.
- [x] Section 6 — EC2 launch with IMDSv2 enforcement; both container and pipx install paths.
- [x] Section 7 — `efterlev init --llm-backend bedrock --llm-region us-gov-west-1 ...`; resulting config TOML shown; honest callout that fallback_model defaults to a commercial-region model name and needs manual update for GovCloud-only deployments.
- [x] Section 8 — egress-block + smoke-run as the no-egress verification check; pointer to SPEC-13 for the automated equivalent.
- [x] Section 9 — running against real Terraform.
- [x] Section 10 — cost-profile callout, explicitly NOT hardcoding numbers that go stale; pointer to AWS pricing page.
- [x] Section 11 — troubleshooting for the five most likely failure modes (AccessDenied, ResourceNotFound, VPC endpoint DNS, credential issues, unintended-egress-still-works).
- [x] Section 12 — further reading, cross-linking SPEC-10/11/13, THREAT_MODEL.md, LIMITATIONS.md, and the canonical AWS docs.
- [x] Tutorial is linked from `README.md`'s Documentation section.

### Maintainer action — pending

- [ ] Walkthrough on a fresh GovCloud account: someone other than the author follows steps 1–9 and reports any ambiguity or broken step.
- [ ] SPEC-13's `EFTERLEV_BEDROCK_SMOKE=1 ... --llm-backend bedrock --llm-region us-gov-west-1` succeeds on the resulting EC2 instance — that's the automated acceptance check.
- [ ] On findings from the walkthrough: amend the tutorial in a follow-up PR. The reproducibility note at the top stays until the walkthrough completes successfully.

## Risks

- **AWS docs change out from under us.** Mitigation: the tutorial links to AWS-owned docs for anything AWS-specific (IAM syntax, Bedrock model access flow) rather than reproducing it. When AWS changes something, only the link needs updating.
- **Bedrock model IDs drift.** Mitigation: the tutorial names specific model IDs but adds "last verified YYYY-MM-DD" stamps. At release cadence, re-verify or bump.
- **Reviewer burden.** A real GovCloud walkthrough requires a reviewer with an AWS GovCloud account, which is not universal. Mitigation: accept that the first walkthrough may be the maintainer alone; a second reviewer can be recruited post-launch through the community.

## Open questions

- Do we ship a companion CloudFormation / Terraform module for the deployment? Answer: no at v0.1.0. The tutorial is the contract; infrastructure-as-code for the setup itself is post-launch if demand surfaces.
- Do we cover the "Efterlev as a systemd service" case for long-running scans? Answer: no at v0.1.0. Efterlev is invoked per scan; daemonization is v1.5+ (tied to the Drift Agent work, SPEC-C1).
