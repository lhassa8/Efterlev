"""Anthropic SDK adapter for `LLMClient`.

Thin wrapper over `anthropic.Anthropic`. Lazy SDK import so the package
imports cleanly in environments without the SDK available (tests that
stub out LLM calls entirely, minimal CI, etc.).

## Retry + fallback (2026-04-23)

A single `complete()` call is NOT a single SDK call. It's an attempt
sequence:

  1. Try the requested `model` up to `_MAX_RETRIES` times, backing off
     exponentially with full jitter between attempts on transient
     errors (rate limits, timeouts, connection resets, 5xx including
     529 overloaded).
  2. If all primary-model attempts fail AND a `fallback_model` is
     configured, try the fallback model ONCE. Fallback failures are
     terminal.
  3. Non-transient errors (auth, bad request, permission denied, not
     found) bypass the retry loop entirely — retrying a 401 is
     pointless and delays the error the user actually needs to see.

The served model's identifier is carried through in `LLMResponse.model`,
so if fallback was used the provenance records accurately show the
model that answered. Each retry and each fallback invocation is logged
at WARNING so users can see transient issues in their scan output.

See DECISIONS 2026-04-23 "Retry + Opus-to-Sonnet fallback" for the
design record.
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from efterlev.errors import AgentError
from efterlev.llm.base import LLMMessage, LLMResponse

if TYPE_CHECKING:  # pragma: no cover
    from anthropic import Anthropic

log = logging.getLogger(__name__)


# Retry budget constants. In-class rather than in config per the
# "keep config small" policy — sensible defaults cover the typical
# transient-error envelope (a minute or two of Anthropic hiccuping).
# If real-world operations reveal these need per-deployment tuning,
# promote them to LLMConfig at that time.
_MAX_RETRIES = 3
_INITIAL_DELAY_SECONDS = 1.0
_MAX_DELAY_SECONDS = 60.0


@dataclass
class AnthropicClient:
    """`LLMClient`-shaped wrapper over the Anthropic Python SDK."""

    api_key: str | None = None
    # Model to fall back to after primary-model retries are exhausted.
    # `None` disables fallback — `complete()` raises the final primary
    # error after all retry attempts. Typical deployments set this to
    # `claude-sonnet-4-6` so an Opus outage doesn't fail the scan.
    fallback_model: str | None = None
    # Injectable sleeper so tests can assert retry behavior without
    # accumulating real backoff delays. Production callers always get
    # `time.sleep`.
    sleeper: Callable[[float], None] = field(default=time.sleep, repr=False)
    _sdk: Any = field(default=None, init=False, repr=False)

    def _client(self) -> Anthropic:
        if self._sdk is None:
            try:
                from anthropic import Anthropic
            except ImportError as e:  # pragma: no cover - guard
                raise AgentError(
                    "anthropic SDK not installed; install `anthropic` or inject a StubLLMClient"
                ) from e
            key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise AgentError(
                    "ANTHROPIC_API_KEY is not set. Export it, or inject a StubLLMClient."
                )
            self._sdk = Anthropic(api_key=key)
        return self._sdk  # type: ignore[no-any-return]

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

        # Primary-model attempts with exponential-backoff-with-jitter on
        # transient errors only. Non-transient errors bypass this loop.
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
                if not _is_retryable(e):
                    raise AgentError(f"anthropic completion failed: {e}") from e
                if attempt < _MAX_RETRIES - 1:
                    delay = _backoff_delay(attempt)
                    log.warning(
                        "anthropic %s attempt %d/%d failed (%s); retrying in %.2fs",
                        model,
                        attempt + 1,
                        _MAX_RETRIES,
                        type(e).__name__,
                        delay,
                    )
                    self.sleeper(delay)
                else:
                    log.warning(
                        "anthropic %s exhausted %d retries on %s",
                        model,
                        _MAX_RETRIES,
                        type(e).__name__,
                    )

        # All primary-model attempts failed. Try fallback ONCE if configured.
        if self.fallback_model and self.fallback_model != model:
            log.warning(
                "anthropic primary model %s failed after %d attempts; falling back to %s",
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
                    "anthropic fallback model %s also failed (%s); raising original error",
                    self.fallback_model,
                    type(fb_error).__name__,
                )

        # No fallback, or fallback also failed — surface the last primary error.
        assert last_error is not None
        raise AgentError(f"anthropic completion failed: {last_error}") from last_error

    def _one_call(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str,
        max_tokens: int,
        prompt_hash: str,
    ) -> LLMResponse:
        """Single SDK call + response validation. Raises SDK exceptions directly."""
        client = self._client()
        # No `temperature` parameter: claude-opus-4-7 (and other modern
        # reasoning-trained models) return 400 "temperature is deprecated
        # for this model" if it's passed. We used to default to
        # temperature=0 for determinism; strict pydantic validation on
        # the LLM's JSON output covers the same concern downstream.
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": m.content} for m in messages],
        )

        # SDK returns a list of content blocks; only `text` blocks are expected
        # for these agents. Concatenate if the model chunked the response.
        parts: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
        if not parts:
            raise AgentError(
                f"anthropic response had no text content (stop_reason={resp.stop_reason!r})"
            )

        # Detect output truncation explicitly: when the model hits max_tokens,
        # the content comes back as valid-so-far text but the JSON our agents
        # expect is almost certainly incomplete. Surfacing this as a distinct
        # error beats letting it fall through to "invalid JSON on line 201"
        # downstream, which has nothing to do with the actual cause.
        if resp.stop_reason == "max_tokens":
            raise AgentError(
                f"anthropic response truncated at max_tokens={max_tokens}. "
                "Increase the max_tokens argument the agent passes to _invoke_llm."
            )

        return LLMResponse(text="".join(parts), model=resp.model, prompt_hash=prompt_hash)


def _is_retryable(error: Exception) -> bool:
    """Classify an exception as a transient backend error vs a permanent one.

    Retryable:
      - `RateLimitError` (429)
      - `APITimeoutError` (network / request timeout)
      - `APIConnectionError` (connection refused, DNS, etc.)
      - `InternalServerError` (5xx, including 529 overloaded)

    Non-retryable (permanent — retry won't help):
      - `AuthenticationError` (401 — bad key)
      - `BadRequestError` (400 — malformed request)
      - `PermissionDeniedError` (403 — wrong scope)
      - `NotFoundError` (404 — bad model name)
      - `UnprocessableEntityError` (422 — schema error)
      - `AgentError` — Efterlev-raised error from response validation
        (truncated output, no text blocks). These are code-level bugs
        or prompt-design issues; retrying is pointless.

    Import is lazy because the anthropic SDK is an optional dep at runtime.
    """
    # Agent-level errors we raised ourselves are never retryable.
    if isinstance(error, AgentError):
        return False

    try:
        import anthropic
    except ImportError:  # pragma: no cover — SDK absent
        # Without the SDK we can't classify SDK exceptions. Be
        # conservative: non-SDK exceptions are not retryable by default
        # (would indicate a test-shim bug anyway).
        return False

    retryable_types: tuple[type[Exception], ...] = (
        anthropic.RateLimitError,
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
        anthropic.InternalServerError,
    )
    return isinstance(error, retryable_types)


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with full jitter. `attempt` is 0-indexed.

    Returns a delay in seconds sampled uniformly from
    [0, min(_MAX_DELAY_SECONDS, _INITIAL_DELAY_SECONDS * 2^attempt)].
    Full jitter is the right choice when many clients could hit the
    same rate-limited resource simultaneously — synchronizes retries
    on a thundering-herd-friendly distribution. See
    https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
    """
    cap = min(_MAX_DELAY_SECONDS, _INITIAL_DELAY_SECONDS * (2**attempt))
    return random.uniform(0, cap)
