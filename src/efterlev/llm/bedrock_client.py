"""AWS Bedrock adapter for `LLMClient`.

Uses the Bedrock Converse API (`bedrock-runtime.converse`) which maps
cleanly onto our existing Anthropic-shaped message format. Lazy boto3
import so `pipx install efterlev` (without the `[bedrock]` extra)
imports cleanly when no Bedrock work is happening.

## Why Bedrock

The open-source launch posture (DECISIONS 2026-04-23 "Rescind closed-
source lock") commits to running anywhere the customer wants — including
inside a FedRAMP-authorized AWS GovCloud boundary, where egress to
`anthropic.com` is the exact thing the boundary is designed to prevent.
Bedrock is the GovCloud-compatible path. See SPEC-10 for full design.

## Retry + fallback

Mirrors the structure of `AnthropicClient`:

  1. Try the requested `model` up to `_MAX_RETRIES` times, backing off
     exponentially with full jitter on transient errors (throttling,
     timeouts, 5xx-equivalent Bedrock service errors).
  2. If all primary attempts fail AND a `fallback_model` is configured,
     try the fallback model ONCE.
  3. Non-transient errors (AccessDenied, Validation, ResourceNotFound)
     bypass the retry loop — retrying a permission error is pointless.

The served model identifier in `LLMResponse.model` reflects which model
actually answered (primary or fallback), so provenance is accurate.

## GovCloud cross-boundary protection

The Bedrock service endpoint is regional: a request to
`bedrock-runtime.us-gov-west-1.amazonaws.com` only hits GovCloud
infrastructure regardless of the requested model ID. The boundary is
held at the AWS endpoint layer, not by us. If an operator configures
a model ID that GovCloud doesn't serve, AWS returns
ResourceNotFoundException (non-retryable in our classifier) and the
operator gets a clean error. We do NOT maintain a model-availability
allowlist — those go stale fast and would generate false negatives.
"""

from __future__ import annotations

import hashlib
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from efterlev.errors import AgentError
from efterlev.llm.base import LLMMessage, LLMResponse

log = logging.getLogger(__name__)


# Match AnthropicClient retry budget so swap-in doesn't change timing
# characteristics for users.
_MAX_RETRIES = 3
_INITIAL_DELAY_SECONDS = 1.0
_MAX_DELAY_SECONDS = 60.0


@dataclass
class AnthropicBedrockClient:
    """`LLMClient`-shaped wrapper over AWS Bedrock's Converse API."""

    region: str
    fallback_model: str | None = None
    aws_profile: str | None = None
    # Injectable sleeper so retry tests don't accumulate real backoff delay.
    sleeper: Callable[[float], None] = field(default=time.sleep, repr=False)
    _client_obj: Any = field(default=None, init=False, repr=False)

    def _client(self) -> Any:
        if self._client_obj is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as e:  # pragma: no cover - guard
                raise AgentError(
                    "boto3 is not installed. Install with "
                    "`pipx install 'efterlev[bedrock]'` or use the container image "
                    "(which has boto3 baked in), or inject a StubLLMClient."
                ) from e
            session = (
                boto3.Session(profile_name=self.aws_profile)
                if self.aws_profile
                else boto3.Session()
            )
            # Gap Agent prompts (60 KSIs * ~75 evidence records + FRMR
            # context) routinely take longer than boto3's default 60s
            # read_timeout on Opus 4.7. The default also retries on its
            # own (max_attempts=3), which multiplies our retry budget
            # against transient errors — we already retry up to 3x in
            # `complete()`. Set both explicitly:
            #   - read_timeout=600s: room for full-baseline classification.
            #   - retries.max_attempts=1: disable boto's retry; ours is
            #     authoritative and emits typed AgentError on exhaustion.
            #   - connect_timeout=10s: catches network setup hangs early.
            # Surfaced by a real first-run Bedrock failure on 2026-04-30.
            client_config = Config(
                read_timeout=600,
                connect_timeout=10,
                retries={"max_attempts": 1},
            )
            self._client_obj = session.client(
                "bedrock-runtime",
                region_name=self.region,
                config=client_config,
            )
        return self._client_obj

    def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        joined = system + "\n".join(m.content for m in messages)
        prompt_hash = hashlib.sha256(joined.encode("utf-8")).hexdigest()

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return self._one_call(
                    system=system,
                    messages=messages,
                    model=model,
                    max_tokens=max_tokens,
                    prompt_hash=prompt_hash,
                )
            except Exception as e:
                last_error = e
                if not _is_retryable_bedrock(e):
                    raise AgentError(f"bedrock completion failed: {e}") from e
                if attempt < _MAX_RETRIES - 1:
                    delay = _backoff_delay(attempt)
                    log.warning(
                        "bedrock %s attempt %d/%d failed (%s); retrying in %.2fs",
                        model,
                        attempt + 1,
                        _MAX_RETRIES,
                        type(e).__name__,
                        delay,
                    )
                    self.sleeper(delay)
                else:
                    log.warning(
                        "bedrock %s exhausted %d retries on %s",
                        model,
                        _MAX_RETRIES,
                        type(e).__name__,
                    )

        if self.fallback_model and self.fallback_model != model:
            log.warning(
                "bedrock primary model %s failed after %d attempts; falling back to %s",
                model,
                _MAX_RETRIES,
                self.fallback_model,
            )
            try:
                return self._one_call(
                    system=system,
                    messages=messages,
                    model=self.fallback_model,
                    max_tokens=max_tokens,
                    prompt_hash=prompt_hash,
                )
            except Exception as fb_error:
                log.warning(
                    "bedrock fallback model %s also failed (%s); raising original error",
                    self.fallback_model,
                    type(fb_error).__name__,
                )

        assert last_error is not None
        raise AgentError(f"bedrock completion failed: {last_error}") from last_error

    def _one_call(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str,
        max_tokens: int,
        prompt_hash: str,
    ) -> LLMResponse:
        """Single Bedrock Converse call + response validation."""
        client = self._client()
        # Converse API maps cleanly onto our system + user-message shape.
        # No `temperature` parameter for the same reason as AnthropicClient:
        # claude-opus-4-7 rejects it, and downstream pydantic validation
        # already enforces output determinism.
        response = client.converse(
            modelId=model,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": m.content}]} for m in messages],
            inferenceConfig={"maxTokens": max_tokens},
        )

        stop_reason = response.get("stopReason", "")
        output = response.get("output", {}).get("message", {})
        content_blocks = output.get("content", [])

        parts: list[str] = []
        for block in content_blocks:
            text = block.get("text")
            if text is not None:
                parts.append(text)
        if not parts:
            raise AgentError(f"bedrock response had no text content (stopReason={stop_reason!r})")

        # Match AnthropicClient: surface max-tokens truncation as a distinct
        # error rather than letting downstream JSON parsing fail mysteriously.
        if stop_reason == "max_tokens":
            raise AgentError(
                f"bedrock response truncated at max_tokens={max_tokens}. "
                "Increase the max_tokens argument the agent passes to _invoke_llm."
            )

        # Bedrock Converse echoes the model in the response metadata; if not
        # present, fall back to the requested model. Per-call requests pin to
        # the exact model that responded (Bedrock doesn't transparently re-route).
        served_model = (
            response.get("ResponseMetadata", {})
            .get("HTTPHeaders", {})
            .get("x-amzn-bedrock-model-id", model)
        )

        return LLMResponse(text="".join(parts), model=served_model, prompt_hash=prompt_hash)


def _is_retryable_bedrock(error: Exception) -> bool:
    """Classify a Bedrock exception as transient vs permanent.

    Retryable:
      - `botocore.exceptions.ReadTimeoutError`
      - `botocore.exceptions.ConnectTimeoutError`
      - `botocore.exceptions.EndpointConnectionError`
      - `botocore.exceptions.ClientError` with a transient error code
        (ThrottlingException, ServiceQuotaExceededException,
        ModelTimeoutException, ServiceUnavailableException,
        InternalServerException, ModelStreamErrorException)

    Non-retryable (permanent):
      - `AgentError` (we raised it ourselves; truncation, no-text, etc.)
      - `ClientError` with permission/validation/not-found codes
        (AccessDeniedException, ValidationException,
        ResourceNotFoundException, ModelNotReadyException)

    Lazy import: botocore is only imported when the classifier is called
    so `efterlev` imports cleanly without the `[bedrock]` extra installed.
    """
    if isinstance(error, AgentError):
        return False

    try:
        from botocore.exceptions import (
            ClientError,
            ConnectTimeoutError,
            EndpointConnectionError,
            ReadTimeoutError,
        )
    except ImportError:  # pragma: no cover — botocore absent
        return False

    if isinstance(error, (ReadTimeoutError, ConnectTimeoutError, EndpointConnectionError)):
        return True

    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code", "")
        retryable_codes = {
            "ThrottlingException",
            "ServiceQuotaExceededException",
            "ModelTimeoutException",
            "ModelStreamErrorException",
            "ServiceUnavailableException",
            "InternalServerException",
        }
        return code in retryable_codes

    return False


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with full jitter. Identical to AnthropicClient's."""
    cap = min(_MAX_DELAY_SECONDS, _INITIAL_DELAY_SECONDS * (2**attempt))
    return random.uniform(0, cap)
