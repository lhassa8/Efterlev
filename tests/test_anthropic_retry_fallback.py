"""Retry + fallback behavior for `AnthropicClient`.

Tests inject a fake SDK into `client._sdk` so no network is touched.
The fake's `messages.create(...)` is programmable: give it a list of
exceptions / responses to emit in order, and it walks the script,
recording which model was requested each call.

Tests assert:
  - Retryable errors trigger retries; non-retryable errors don't.
  - Retries back off via the injected `sleeper` callable (no real sleep).
  - Fallback fires only after primary retries are exhausted.
  - Successful first attempt, successful retry, and successful fallback
    paths each return the response that actually arrived.
  - Retry-exhausted AND fallback-failed raises the original primary error.

See DECISIONS 2026-04-23 "Retry + Opus-to-Sonnet fallback".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from efterlev.errors import AgentError
from efterlev.llm.anthropic_client import AnthropicClient
from efterlev.llm.base import LLMMessage

# --- fake SDK ----------------------------------------------------------------


@dataclass
class _FakeContentBlock:
    text: str


@dataclass
class _FakeResponse:
    content: list[_FakeContentBlock]
    model: str
    stop_reason: str = "end_turn"


@dataclass
class _FakeMessages:
    """Walks a scripted list of outcomes on each `.create(...)` call.

    Each script item is either a callable `fn(model) -> _FakeResponse` (for
    success cases that care about which model was requested) or an
    exception class to raise.
    """

    script: list[Any]
    calls: list[dict] = field(default_factory=list)

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if not self.script:
            raise RuntimeError("fake SDK script exhausted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(kwargs["model"])  # type: ignore[no-any-return]
        assert isinstance(item, _FakeResponse)
        return item


@dataclass
class _FakeSdk:
    messages: _FakeMessages


def _ok_response(text: str = '{"ok": true}', model: str = "claude-opus-4-7") -> _FakeResponse:
    return _FakeResponse(content=[_FakeContentBlock(text=text)], model=model)


def _make_client(
    *,
    script: list[Any],
    fallback_model: str | None = None,
) -> tuple[AnthropicClient, _FakeMessages, list[float]]:
    slept: list[float] = []
    fake_msgs = _FakeMessages(script=script)
    client = AnthropicClient(
        api_key="test-key",
        fallback_model=fallback_model,
        sleeper=slept.append,
    )
    client._sdk = _FakeSdk(messages=fake_msgs)
    return client, fake_msgs, slept


# --- helpers to create anthropic SDK exceptions -----------------------------
# The SDK requires specific constructor shapes for each exception class.
# Building them at test time keeps the tests tight and honest about which
# exception classes we're claiming to handle.


def _rate_limit_error() -> Exception:
    import anthropic
    from httpx import Request, Response

    request = Request("POST", "https://api.anthropic.com/v1/messages")
    response = Response(status_code=429, request=request)
    return anthropic.RateLimitError("rate limited", response=response, body=None)


def _connection_error() -> Exception:
    import anthropic
    from httpx import Request

    request = Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(request=request)


def _internal_server_error() -> Exception:
    import anthropic
    from httpx import Request, Response

    request = Request("POST", "https://api.anthropic.com/v1/messages")
    response = Response(status_code=529, request=request)
    return anthropic.InternalServerError("overloaded", response=response, body=None)


def _auth_error() -> Exception:
    import anthropic
    from httpx import Request, Response

    request = Request("POST", "https://api.anthropic.com/v1/messages")
    response = Response(status_code=401, request=request)
    return anthropic.AuthenticationError("invalid x-api-key", response=response, body=None)


def _bad_request_error() -> Exception:
    import anthropic
    from httpx import Request, Response

    request = Request("POST", "https://api.anthropic.com/v1/messages")
    response = Response(status_code=400, request=request)
    return anthropic.BadRequestError("bad input", response=response, body=None)


# --- success-first-attempt -------------------------------------------------


def test_first_attempt_success_returns_response_no_retries() -> None:
    client, msgs, slept = _make_client(script=[_ok_response()])
    resp = client.complete(
        system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7"
    )
    assert resp.text == '{"ok": true}'
    assert len(msgs.calls) == 1
    assert slept == []  # no backoff sleeps


# --- retry paths ------------------------------------------------------------


def test_rate_limit_then_success_retries_and_returns() -> None:
    client, msgs, slept = _make_client(
        script=[_rate_limit_error(), _ok_response()]
    )
    resp = client.complete(
        system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7"
    )
    assert resp.text == '{"ok": true}'
    assert len(msgs.calls) == 2
    assert len(slept) == 1  # one backoff between attempts
    assert slept[0] >= 0  # non-negative jittered delay


def test_connection_error_is_retryable() -> None:
    client, msgs, _ = _make_client(script=[_connection_error(), _ok_response()])
    client.complete(system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7")
    assert len(msgs.calls) == 2


def test_internal_server_529_is_retryable() -> None:
    client, msgs, _ = _make_client(script=[_internal_server_error(), _ok_response()])
    client.complete(system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7")
    assert len(msgs.calls) == 2


def test_all_retries_exhausted_no_fallback_raises() -> None:
    # 3 retryable errors, no fallback — all attempts exhausted; last error raised.
    client, msgs, slept = _make_client(
        script=[_rate_limit_error(), _rate_limit_error(), _rate_limit_error()]
    )
    with pytest.raises(AgentError, match="anthropic completion failed"):
        client.complete(
            system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7"
        )
    assert len(msgs.calls) == 3
    # Two backoffs: between attempts 1→2 and 2→3. No sleep after the final
    # attempt (nothing left to wait for).
    assert len(slept) == 2


# --- non-retryable errors ----------------------------------------------------


def test_auth_error_no_retry_immediate_raise() -> None:
    client, msgs, slept = _make_client(
        script=[_auth_error()]  # only one item — proves no retries attempted
    )
    with pytest.raises(AgentError, match="anthropic completion failed"):
        client.complete(
            system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7"
        )
    assert len(msgs.calls) == 1
    assert slept == []


def test_bad_request_no_retry() -> None:
    client, msgs, _ = _make_client(script=[_bad_request_error()])
    with pytest.raises(AgentError):
        client.complete(
            system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7"
        )
    assert len(msgs.calls) == 1


# --- fallback paths ---------------------------------------------------------


def test_primary_exhausted_fallback_succeeds() -> None:
    # 3 retryable errors on primary, then a success on fallback.
    client, msgs, _ = _make_client(
        script=[
            _rate_limit_error(),
            _rate_limit_error(),
            _rate_limit_error(),
            _ok_response(text='{"from": "sonnet"}', model="claude-sonnet-4-6"),
        ],
        fallback_model="claude-sonnet-4-6",
    )
    resp = client.complete(
        system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7"
    )
    assert resp.text == '{"from": "sonnet"}'
    assert resp.model == "claude-sonnet-4-6"  # provenance reflects served model
    assert len(msgs.calls) == 4
    # Verify the fallback call requested the fallback model.
    assert msgs.calls[-1]["model"] == "claude-sonnet-4-6"
    # The first three calls were to the primary.
    assert all(c["model"] == "claude-opus-4-7" for c in msgs.calls[:3])


def test_primary_exhausted_fallback_also_fails_raises_original() -> None:
    client, msgs, _ = _make_client(
        script=[
            _rate_limit_error(),
            _rate_limit_error(),
            _rate_limit_error(),
            _rate_limit_error(),  # fallback also fails
        ],
        fallback_model="claude-sonnet-4-6",
    )
    with pytest.raises(AgentError, match="anthropic completion failed"):
        client.complete(
            system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7"
        )
    assert len(msgs.calls) == 4


def test_fallback_skipped_when_primary_equals_fallback() -> None:
    # If somebody configured fallback_model to the same value as the
    # requested model, there's no point calling a "fallback" that IS
    # the primary. This test locks in that short-circuit.
    client, msgs, _ = _make_client(
        script=[_rate_limit_error(), _rate_limit_error(), _rate_limit_error()],
        fallback_model="claude-opus-4-7",  # same as request
    )
    with pytest.raises(AgentError):
        client.complete(
            system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7"
        )
    assert len(msgs.calls) == 3  # no extra fallback call


def test_no_retry_on_auth_even_if_fallback_configured() -> None:
    # Auth errors indicate user-side config problems; fallback is pointless
    # and would just swap to a different 401. Fail fast.
    client, msgs, slept = _make_client(
        script=[_auth_error()],  # one item: proves no retry and no fallback
        fallback_model="claude-sonnet-4-6",
    )
    with pytest.raises(AgentError):
        client.complete(
            system="s", messages=[LLMMessage(content="m")], model="claude-opus-4-7"
        )
    assert len(msgs.calls) == 1
    assert slept == []


# --- backoff math -----------------------------------------------------------


def test_backoff_delay_is_bounded_by_cap() -> None:
    from efterlev.llm.anthropic_client import _MAX_DELAY_SECONDS, _backoff_delay

    # Large attempt number must still respect the cap — exponential
    # growth shouldn't produce a 30-minute sleep on attempt 20.
    for attempt in range(25):
        delay = _backoff_delay(attempt)
        assert 0 <= delay <= _MAX_DELAY_SECONDS


def test_backoff_delay_zero_attempt_sane() -> None:
    from efterlev.llm.anthropic_client import _INITIAL_DELAY_SECONDS, _backoff_delay

    # Attempt 0 → [0, _INITIAL_DELAY_SECONDS].
    for _ in range(20):
        d = _backoff_delay(0)
        assert 0 <= d <= _INITIAL_DELAY_SECONDS
