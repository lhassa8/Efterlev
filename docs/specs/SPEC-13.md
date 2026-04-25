# SPEC-13: Bedrock smoke test in e2e harness

**Status:** implemented 2026-04-24 (real-Bedrock acceptance run pending maintainer credentials)
**Gate:** A3
**Depends on:** SPEC-10 (AnthropicBedrockClient — implemented), SPEC-11 (config surface — implemented)
**Blocks:** SPEC-12 acceptance (tutorial's no-egress step uses this test's invocation pattern)
**Size:** S

## Goal

Extend the existing end-to-end smoke harness at `scripts/e2e_smoke.py` so it can run the full agent pipeline against AWS Bedrock (as an alternative to Anthropic-direct), confirming the Bedrock backend works in the same shape as the primary backend. This is the automated check that backs SPEC-10's "runs against real Bedrock" exit criterion.

## Scope

- New `--llm-backend bedrock` flag on `scripts/e2e_smoke.py`, default `anthropic`.
- New env-gate: `EFTERLEV_BEDROCK_SMOKE=1` + `AWS_PROFILE` or `AWS_ACCESS_KEY_ID` required for the Bedrock path; skip otherwise with an exit-2 "not configured" signal (matching the existing Anthropic-API-key skip semantics).
- Runs the same three agents (Gap, Documentation, Remediation) against the same fixture the harness already uses.
- Check set: identical to the existing Anthropic-direct checks. No Bedrock-specific output validation beyond "the run completed and produced the same artifact shapes."
- Results land in `.e2e-results/<UTC-timestamp>-bedrock/` (distinguishable from the Anthropic-direct run directory).
- Optional `--llm-region` flag for explicit region selection; defaults to `AWS_REGION` env.

## Non-goals

- A separate fixture dedicated to Bedrock. The existing e2e fixture is sufficient; Bedrock is an LLM backend swap, not a new detector surface.
- Response-parity assertion (same byte output for same prompt across backends). LLM outputs vary slightly; structural parity is the meaningful check, already covered by the existing check set.
- Cost reporting in the harness. Bedrock token costs are visible in the AWS console; we don't duplicate.
- Running both backends in the same invocation for cost comparison. Separate runs keep the harness simple; compare offline.
- Bedrock Guardrails. Orthogonal to the smoke path.

## Interface

`scripts/e2e_smoke.py` new flags:

```
--llm-backend {anthropic,bedrock}   # default: anthropic
--llm-region REGION                 # required when --llm-backend=bedrock; or AWS_REGION env
--llm-model MODEL                   # optional; defaults per backend
```

Invocation examples:

```bash
# Existing Anthropic-direct smoke — unchanged behavior
ANTHROPIC_API_KEY=sk-ant-... scripts/e2e_smoke.py

# New Bedrock smoke (commercial)
EFTERLEV_BEDROCK_SMOKE=1 AWS_PROFILE=efterlev-dev \
  scripts/e2e_smoke.py --llm-backend bedrock --llm-region us-east-1

# New Bedrock smoke (GovCloud)
EFTERLEV_BEDROCK_SMOKE=1 AWS_PROFILE=efterlev-govcloud \
  scripts/e2e_smoke.py --llm-backend bedrock \
    --llm-region us-gov-west-1 \
    --llm-model us.anthropic.claude-opus-4-7-v1:0
```

Exit codes match existing e2e behavior:
- 0 — all checks passed
- 1 — at least one critical check failed
- 2 — skipped (Bedrock envs unset when `--llm-backend=bedrock`)

## Behavior

- Bedrock path instantiates `AnthropicBedrockClient` (SPEC-10) with the configured region / model.
- All three agents run through the same reasoning paths; the only thing that changes is the LLM client factory returns a Bedrock client instead of Anthropic-direct.
- Check set reused verbatim — the existing `critical` / `quality` / `info` severity buckets apply identically.
- Results-directory naming disambiguates runs: `.e2e-results/20260424T140530Z-bedrock-us-gov-west-1/` for a GovCloud-region run.
- On skip (`EFTERLEV_BEDROCK_SMOKE=1` unset with `--llm-backend=bedrock`), prints a clear message and exits 2.
- On AWS-credential failure, prints the AWS error verbatim (don't obscure) and exits 1.

## Data / schema

- No new output schemas. Results directories are existing e2e harness shape with a `-bedrock` suffix.
- `checks.json` and `summary.md` generation unchanged.

## Test plan

- **Unit (harness itself):** argparse accepts the new flags; defaults work; skip logic triggers correctly when env missing.
- **Integration (real Bedrock, gated):** a maintainer runs the smoke against both commercial and GovCloud Bedrock regions; both complete successfully.
- **Regression:** existing Anthropic-direct smoke continues to pass after the harness modifications.
- **CI:** e2e harness is already pytest-wrapped at `tests/test_e2e_smoke.py`; a new wrapper test `tests/test_e2e_smoke_bedrock.py` gates on the same env-skip pattern and runs only when explicitly enabled.

## Exit criterion

### Implementation landed 2026-04-24

- [x] `scripts/e2e_smoke.py` accepts `--llm-backend`, `--llm-region`, `--llm-model` via argparse. Backend selector is `choices=["anthropic", "bedrock"]`; default `anthropic` preserves existing behavior.
- [x] `_check_backend_env(backend, region)` enforces backend-specific skip gates: anthropic requires `ANTHROPIC_API_KEY`; bedrock requires `EFTERLEV_BEDROCK_SMOKE=1` AND AWS creds (`AWS_PROFILE` or `AWS_ACCESS_KEY_ID`) AND a region (`--llm-region` or `AWS_REGION`). Each missing-prerequisite path returns exit 2 with a clear message naming what's missing.
- [x] `efterlev init` invocation in the harness is now backend-aware: passes `--llm-backend`, `--llm-region` (when bedrock), and `--llm-model`. All subsequent agent stages read the resulting `.efterlev/config.toml` and dispatch via SPEC-10's factory automatically — no agent-specific changes needed.
- [x] Results directory naming disambiguates: `.e2e-results/<UTC-ISO>-bedrock-<region>/` for non-anthropic runs.
- [x] `tests/test_e2e_smoke_bedrock.py` pytest wrapper. Skips when prerequisites are missing; promotes harness-side skip (exit 2) to a pytest skip rather than a failure.
- [x] `pyproject.toml` registers the `e2e` pytest marker so `--strict-markers` accepts both wrappers.
- [x] Manually verified all four skip paths exit 2 with correct messages: anthropic-no-key; bedrock-no-opt-in; bedrock-opt-in-no-creds; bedrock-creds-no-region.
- [x] Anthropic-direct path unchanged: existing `tests/test_e2e_smoke.py` wrapper continues to drive the same code path.

### Maintainer action — pending

- [ ] Run `EFTERLEV_BEDROCK_SMOKE=1 AWS_PROFILE=<dev> uv run python scripts/e2e_smoke.py --llm-backend bedrock --llm-region us-east-1`. Confirm green and that the results directory at `.e2e-results/<ts>-bedrock-us-east-1/summary.md` shows the expected check pass set.
- [ ] Run the same against `us-gov-west-1` from a GovCloud EC2 instance configured per SPEC-12. Confirm green; this is the proof point for SPEC-12's tutorial.

## Risks

- **Bedrock model-availability delays.** Same as SPEC-10: if a specific Opus model ID isn't available in GovCloud yet, the smoke fails with a clear error and the maintainer picks an available model. Not a blocker for the SPEC's acceptance; the smoke is the mechanism by which we discover availability gaps.
- **AWS credential misconfiguration during smoke runs.** Mitigation: clear error pass-through; SPEC-12 troubleshooting section covers the common failure modes.
- **Cost of running the smoke.** A single Gap+Documentation+Remediation pass on the fixture is roughly the same cost as the existing Anthropic-direct smoke (~$1-2). Acceptable.

## Open questions

None.
