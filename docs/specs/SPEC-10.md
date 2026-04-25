# SPEC-10: AnthropicBedrockClient — AWS Bedrock LLM backend

**Status:** implemented 2026-04-24 (real-Bedrock acceptance test deferred to SPEC-13's first dry-run)
**Gate:** A3 (Bedrock backend; pre-launch readiness)
**Depends on:** SPEC-11 (`LLMConfig.backend`/`region` config surface — implemented), none else (uses existing `LLMClient` base in `src/efterlev/llm/base.py`)
**Blocks:** SPEC-12 (GovCloud deploy tutorial — unblocked), SPEC-13 (Bedrock smoke test — unblocked)
**Size:** M

## Goal

Efterlev's agents call Claude via AWS Bedrock in commercial AWS or AWS GovCloud regions, so the tool runs inside a FedRAMP-authorized boundary without egress to `anthropic.com`. This is the deployability commitment that makes the "runs where the customer wants" promise in the open-source launch posture real for GovCloud-bound users.

## Scope

- New `AnthropicBedrockClient` class implementing the existing `LLMClient` protocol used by Gap, Documentation, and Remediation agents.
- Supports both commercial AWS Bedrock and AWS GovCloud Bedrock regions.
- Model ID, region, AWS credentials, and other parameters configurable.
- Respects the existing retry + Opus→Sonnet fallback behavior from the 2026-04-23 `AnthropicClient` rewrite.
- Same message/response contract as `AnthropicClient` so agents are backend-agnostic.
- `get_default_client()` factory in `src/efterlev/llm/factory.py` dispatches to the right backend based on `LLMConfig.backend`.
- GovCloud safety check: client refuses to dispatch to a non-GovCloud model ID when configured with a GovCloud region.

## Non-goals

- Other LLM backends (Ollama, vLLM, OpenAI, Gemini). Separate specs if customer-pulled.
- Auto-discovery of the best region or model. Caller configures explicitly.
- Cost-optimization routing (commercial vs GovCloud based on data sensitivity). Fixed per-config.
- Bedrock prompt caching. Post-launch optimization if it lands.
- CloudWatch or AWS-X-Ray tracing integration.
- Bedrock Guardrails (AWS's content-moderation layer — orthogonal to Efterlev's own prompt scrubbing).

## Interface

Class surface:

```python
class AnthropicBedrockClient(LLMClient):
    def __init__(
        self,
        model: str,                         # e.g. "us.anthropic.claude-opus-4-7-v1:0"
        *,
        region: str,                        # e.g. "us-east-1" or "us-gov-west-1"
        fallback_model: str | None = None,  # e.g. "us.anthropic.claude-sonnet-4-6-v1:0"
        max_tokens: int = 4096,
        temperature: float = 0.0,
        timeout_seconds: float = 60.0,
        aws_profile: str | None = None,     # None = default credential chain
        sleeper: Callable[[float], None] = time.sleep,  # injectable for tests
    ) -> None: ...

    def complete(self, system: str, messages: list[Message]) -> LLMResponse: ...
```

Config surface (owned by SPEC-11):

```toml
[llm]
backend = "bedrock"                              # was implicitly "anthropic"
model = "us.anthropic.claude-opus-4-7-v1:0"
region = "us-gov-west-1"                         # required when backend=bedrock
fallback_model = "us.anthropic.claude-sonnet-4-6-v1:0"
```

Factory dispatch:

```python
# src/efterlev/llm/factory.py
def get_default_client() -> LLMClient:
    config = load_config().llm
    if config.backend == "bedrock":
        return AnthropicBedrockClient(
            model=config.model,
            region=config.region,                # SPEC-11 enforces non-None when backend=bedrock
            fallback_model=config.fallback_model or None,
        )
    return AnthropicClient(
        model=config.model,
        fallback_model=config.fallback_model or None,
    )
```

## Behavior

- `backend="bedrock"` → factory instantiates `AnthropicBedrockClient` instead of `AnthropicClient`. No agent code changes.
- Uses `boto3.client("bedrock-runtime", region_name=region)` with the Converse API (not InvokeModel) so messages map cleanly to the Anthropic message format agents already produce.
- Retry behavior: `ThrottlingException`, `ServiceQuotaExceededException`, `ModelTimeoutException`, `ModelErrorException` (5xx) are retryable. Exponential backoff with full jitter. Max 3 attempts on primary, 1 attempt on `fallback_model` if set.
- Non-retryable errors: `AccessDeniedException`, `ValidationException`, `ResourceNotFoundException` — fail immediately with `LLMError`.
- If `fallback_model` is unset, exhausting primary retries raises `LLMError`.
- GovCloud safety check: when `region` matches `^us-gov-`, the client verifies the model ID is Bedrock-GovCloud-available before dispatching. If `model` is a commercial-only ID, raises `LLMError` before any network call. Prevents accidental cross-boundary traffic.
- Every LLM call emits the same provenance metadata as the Anthropic-direct client (model ID, completion tokens, usage, request ID in vendor-extensions).
- Secret redaction (SPEC from earlier 2026-04-23) runs unconditionally on the prompt before Bedrock dispatch — same pipeline, different egress destination.

## Data / schema

- No new on-disk schema. Provenance records store the Bedrock model ID in the existing `model_id` field; the `backend` goes in a new `vendor` field (default `"anthropic"` for direct, `"bedrock"` for this client). Migration-free — existing records without `vendor` continue to read correctly (Pydantic default).
- No config migration. Existing configs with `backend = "anthropic"` work unchanged; the `region` field is only required when `backend = "bedrock"` (SPEC-11).

## Test plan

- **Unit:** mock `bedrock-runtime` client; verify
  - message-shape translation (Anthropic Converse API);
  - retry classifier (each AWS error type routes correctly);
  - fallback trigger after 3 primary attempts;
  - GovCloud safety check: commercial model ID + `us-gov-*` region → raises before `boto3` call;
  - credential-chain behavior with and without `aws_profile`.
- **Integration:** real Bedrock call gated on `EFTERLEV_BEDROCK_TEST=1` + `AWS_PROFILE`. Skips by default. Runs in e2e harness when envs set. Matches SPEC-13 scope.
- **Failure-mode:** inject `ThrottlingException` → retry succeeds on attempt 2; inject repeated `ThrottlingException` → fallback fires; inject `AccessDeniedException` → fails immediately; GovCloud-region + commercial model → raises `LLMError` before dispatch.
- **Response parity:** smoke comparison — identical prompt to both backends produces responses of similar shape (not identical bytes; the test checks structural parity, not content).
- **Secret-redaction pass-through:** prompts sent via Bedrock must go through the same scrubber as Anthropic-direct; test asserts scrubber-modified text appears in the Bedrock-sent payload.

## Exit criterion

### Implementation landed 2026-04-24

- [x] `AnthropicBedrockClient` class exists at `src/efterlev/llm/bedrock_client.py`. Same dataclass shape and retry-budget constants as `AnthropicClient` so behavior swap is symmetric.
- [x] `src/efterlev/llm/factory.py` rewritten to dispatch on `LLMConfig.backend`. New public `get_client_from_config(LLMConfig)` for explicit-config paths; `get_default_client()` walks up from cwd looking for `.efterlev/config.toml` and dispatches automatically. Falls back to anthropic defaults when no workspace is reachable (preserves v0 behavior for ad-hoc scripts and unit tests).
- [x] `src/efterlev/llm/__init__.py` exports `AnthropicBedrockClient` and `get_client_from_config`.
- [x] `pyproject.toml`: `boto3>=1.35,<2` added as `[bedrock]` extra (opt-in for non-GovCloud users) AND in `[dev]` so tests can mock botocore exception classes.
- [x] `Dockerfile` installs the wheel with the `[bedrock]` extra, so the container image is GovCloud-ready out of the box.
- [x] 16 unit tests in `tests/test_bedrock_client.py` cover happy paths (single + multi-block response, message-shape translation), response-validation failures (max-tokens truncation, no-text-blocks), retry behavior (transient-then-success, exhausted-without-fallback, fallback-after-exhaustion, fallback-also-failing-raises-original), non-retryable errors (AccessDenied, Validation, ResourceNotFound), retry classifier (each AWS error code), network errors (ReadTimeout/ConnectTimeout/EndpointConnectionError), backoff bounds.
- [x] 11 unit tests in `tests/test_llm_factory.py` cover `get_client_from_config` dispatch (anthropic, bedrock, fallback-pass-through, empty-string-fallback, defensive-region-check), `get_default_client` workspace-walk behavior (no-workspace, workspace-cwd, walk-up-from-subdir, malformed-config-tolerated), and the `_find_workspace_config` helper.
- [x] All 496 tests pass (was 469 before SPEC-10; +27 new). ruff clean. ruff format clean. mypy clean across 97 source files.
- [x] `LIMITATIONS.md` previously had no explicit Bedrock-deferred entry (the deferral lived in DECISIONS and the v1 plan); README's "Soon" and "Not in scope" sections updated to mark Bedrock shipped.

### Real-Bedrock acceptance — owned by SPEC-13

End-to-end verification against actual AWS Bedrock requires AWS credentials and a configured Bedrock account. Per the e2e harness pattern, real-API integration is gated on `EFTERLEV_BEDROCK_SMOKE=1` + `AWS_PROFILE` and skipped by default. SPEC-13 owns that exit criterion. The unit tests with mocked boto3 are sufficient to ship the implementation.

## Revision 2026-04-24: GovCloud safety pre-check moved to "trust AWS-side rejection"

The draft said: "GovCloud safety check: when `region` matches `^us-gov-`, the client verifies the model ID is Bedrock-GovCloud-available before dispatching."

Implementation reality: maintaining a model-availability allowlist for GovCloud would require ongoing maintenance and would generate false negatives whenever AWS expanded GovCloud Bedrock's supported model set. The actual cross-boundary protection comes from the regional Bedrock endpoint itself (`bedrock-runtime.us-gov-west-1.amazonaws.com` only hits GovCloud infrastructure regardless of the requested model ID), so the boundary is held by AWS, not by us.

If an operator misconfigures the model ID, AWS returns `ResourceNotFoundException` which our retry classifier correctly treats as non-retryable. The operator gets an immediate clean error with the AWS-side reason. No data crosses the boundary.

The module docstring documents this explicitly under "GovCloud cross-boundary protection."

## Risks

- **Bedrock Converse API semantics differ from Anthropic-direct in edge cases** (system-prompt handling, stop sequences, partial-streaming behavior). Mitigation: response-parity smoke compares identical prompts through both backends; divergence caught pre-launch.
- **GovCloud model availability lags commercial.** Mitigation: model-ID list is config, not hardcoded; we document which models are available in which regions as of last verification and refresh on catalog bumps.
- **boto3 dependency growth.** ~17 MB installed. Acceptable for a compliance tool aimed at GovCloud. Mitigation: gate behind `efterlev[bedrock]` extra if installation size matters to non-GovCloud users.
- **Bedrock cost multiplier.** Bedrock charges per million tokens at a different rate than Anthropic-direct; users should know before switching. Mitigation: `docs/RELEASE.md` and the GovCloud deploy doc (SPEC-12) state the cost-profile difference explicitly.
- **AWS SDK authentication surprises.** The default credential chain behavior varies (IMDS on EC2, profile on laptop, env on CI). Mitigation: explicit test matrix covering each credential path; documented troubleshooting in SPEC-12.

## Open questions

- Should `boto3` be a direct dep or gated behind `efterlev[bedrock]`? Defer decision to implementation time; first pass direct-dep, measure wheel size, reconsider if it exceeds 30 MB.
- Should the GovCloud-safety check be hard-fail or warning? Hard-fail. An accidental commercial-model request in GovCloud isn't just a cost issue — it's a boundary-crossing event that could fail 3PAO review.
