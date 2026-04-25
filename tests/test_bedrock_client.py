"""Tests for `AnthropicBedrockClient` (SPEC-10).

Mocks the boto3 bedrock-runtime client so the retry/fallback/error-
classification logic is exercised without real AWS. Real Bedrock
integration is the responsibility of SPEC-13 (e2e harness Bedrock path),
gated on env vars and skipped by default.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from efterlev.errors import AgentError
from efterlev.llm.base import LLMMessage
from efterlev.llm.bedrock_client import (
    AnthropicBedrockClient,
    _backoff_delay,
    _is_retryable_bedrock,
)

# --- helpers ---------------------------------------------------------


def _converse_response(text: str = "ok", stop_reason: str = "end_turn") -> dict[str, Any]:
    """Build a minimal Bedrock Converse API response shape."""
    return {
        "stopReason": stop_reason,
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "ResponseMetadata": {
            "HTTPHeaders": {"x-amzn-bedrock-model-id": "us.anthropic.claude-opus-4-7-v1:0"},
        },
    }


def _client_error(code: str) -> Exception:
    """Build a botocore ClientError with the given Bedrock error code."""
    from botocore.exceptions import ClientError

    return ClientError(
        error_response={"Error": {"Code": code, "Message": f"simulated {code}"}},
        operation_name="Converse",
    )


def _bedrock_with_mock(
    *,
    region: str = "us-east-1",
    fallback_model: str | None = None,
    canned: list[Any] | None = None,
) -> tuple[AnthropicBedrockClient, MagicMock]:
    """Construct a client with a pre-injected mock boto3 bedrock-runtime."""
    client = AnthropicBedrockClient(
        region=region,
        fallback_model=fallback_model,
        sleeper=lambda _: None,
    )
    fake = MagicMock()
    if canned:
        # Each entry is either a response dict (returned) or an exception (raised).
        side_effects: list[Any] = list(canned)
        fake.converse.side_effect = side_effects
    client._client_obj = fake  # type: ignore[assignment]
    return client, fake


# --- happy paths -----------------------------------------------------


def test_complete_returns_response_text() -> None:
    client, fake = _bedrock_with_mock(canned=[_converse_response("hello world")])
    resp = client.complete(
        system="sys",
        messages=[LLMMessage(content="hi")],
        model="us.anthropic.claude-opus-4-7-v1:0",
    )
    assert resp.text == "hello world"
    assert resp.model == "us.anthropic.claude-opus-4-7-v1:0"
    assert resp.prompt_hash  # populated
    assert fake.converse.call_count == 1


def test_complete_concatenates_multi_block_response() -> None:
    """Multi-block responses (rare but possible per Bedrock docs)."""
    multi = _converse_response("first ")
    multi["output"]["message"]["content"] = [{"text": "first "}, {"text": "second"}]
    client, _ = _bedrock_with_mock(canned=[multi])
    resp = client.complete(
        system="sys",
        messages=[LLMMessage(content="hi")],
        model="m",
    )
    assert resp.text == "first second"


def test_complete_passes_system_and_messages_to_converse() -> None:
    client, fake = _bedrock_with_mock(canned=[_converse_response("ok")])
    client.complete(
        system="be helpful",
        messages=[LLMMessage(content="hello"), LLMMessage(content="follow up")],
        model="m",
    )
    call_kwargs = fake.converse.call_args.kwargs
    assert call_kwargs["modelId"] == "m"
    assert call_kwargs["system"] == [{"text": "be helpful"}]
    assert call_kwargs["messages"] == [
        {"role": "user", "content": [{"text": "hello"}]},
        {"role": "user", "content": [{"text": "follow up"}]},
    ]
    assert call_kwargs["inferenceConfig"] == {"maxTokens": 4096}


# --- response-validation failures ------------------------------------


def test_max_tokens_truncation_raises() -> None:
    truncated = _converse_response("partial", stop_reason="max_tokens")
    client, _ = _bedrock_with_mock(canned=[truncated])
    with pytest.raises(AgentError, match="truncated at max_tokens"):
        client.complete(system="s", messages=[LLMMessage("x")], model="m")


def test_no_text_blocks_raises() -> None:
    empty = _converse_response("")
    empty["output"]["message"]["content"] = []
    client, _ = _bedrock_with_mock(canned=[empty])
    with pytest.raises(AgentError, match="no text content"):
        client.complete(system="s", messages=[LLMMessage("x")], model="m")


# --- retry behavior --------------------------------------------------


def test_retry_on_throttling_then_success() -> None:
    """Transient ThrottlingException retries and the second attempt succeeds."""
    client, fake = _bedrock_with_mock(
        canned=[_client_error("ThrottlingException"), _converse_response("ok")],
    )
    resp = client.complete(system="s", messages=[LLMMessage("x")], model="m")
    assert resp.text == "ok"
    assert fake.converse.call_count == 2


def test_retry_exhausted_without_fallback_raises() -> None:
    """3 throttling errors + no fallback configured → AgentError."""
    client, fake = _bedrock_with_mock(
        canned=[_client_error("ThrottlingException")] * 3,
    )
    with pytest.raises(AgentError, match="bedrock completion failed"):
        client.complete(system="s", messages=[LLMMessage("x")], model="m")
    assert fake.converse.call_count == 3


def test_fallback_after_primary_exhausted() -> None:
    """3 primary throttles → fallback model attempted once → success on fallback."""
    client, fake = _bedrock_with_mock(
        fallback_model="us.anthropic.claude-sonnet-4-6-v1:0",
        canned=[
            _client_error("ThrottlingException"),
            _client_error("ThrottlingException"),
            _client_error("ThrottlingException"),
            _converse_response("from fallback"),
        ],
    )
    resp = client.complete(system="s", messages=[LLMMessage("x")], model="m-primary")
    assert resp.text == "from fallback"
    assert fake.converse.call_count == 4
    fallback_call = fake.converse.call_args_list[3].kwargs
    assert fallback_call["modelId"] == "us.anthropic.claude-sonnet-4-6-v1:0"


def test_fallback_also_failing_raises_original_error() -> None:
    """Primary exhausts retries, fallback also fails — the original error surfaces."""
    client, fake = _bedrock_with_mock(
        fallback_model="us.anthropic.claude-sonnet-4-6-v1:0",
        canned=[_client_error("ThrottlingException")] * 4,
    )
    with pytest.raises(AgentError, match="bedrock completion failed"):
        client.complete(system="s", messages=[LLMMessage("x")], model="m")
    assert fake.converse.call_count == 4


# --- non-retryable errors --------------------------------------------


def test_no_retry_on_access_denied() -> None:
    """AccessDeniedException is permanent — fail immediately, no retry."""
    client, fake = _bedrock_with_mock(canned=[_client_error("AccessDeniedException")])
    with pytest.raises(AgentError, match="bedrock completion failed"):
        client.complete(system="s", messages=[LLMMessage("x")], model="m")
    assert fake.converse.call_count == 1


def test_no_retry_on_validation_error() -> None:
    client, fake = _bedrock_with_mock(canned=[_client_error("ValidationException")])
    with pytest.raises(AgentError):
        client.complete(system="s", messages=[LLMMessage("x")], model="m")
    assert fake.converse.call_count == 1


def test_no_retry_on_resource_not_found() -> None:
    """ResourceNotFoundException is the GovCloud cross-boundary signal."""
    client, fake = _bedrock_with_mock(canned=[_client_error("ResourceNotFoundException")])
    with pytest.raises(AgentError):
        client.complete(system="s", messages=[LLMMessage("x")], model="m")
    assert fake.converse.call_count == 1


# --- classifier directly ---------------------------------------------


def test_is_retryable_bedrock_classifies_correctly() -> None:
    assert _is_retryable_bedrock(_client_error("ThrottlingException")) is True
    assert _is_retryable_bedrock(_client_error("ServiceQuotaExceededException")) is True
    assert _is_retryable_bedrock(_client_error("ModelTimeoutException")) is True
    assert _is_retryable_bedrock(_client_error("InternalServerException")) is True
    assert _is_retryable_bedrock(_client_error("AccessDeniedException")) is False
    assert _is_retryable_bedrock(_client_error("ValidationException")) is False
    assert _is_retryable_bedrock(_client_error("ResourceNotFoundException")) is False
    assert _is_retryable_bedrock(AgentError("self-raised, never retry")) is False


def test_is_retryable_bedrock_handles_network_errors() -> None:
    """ReadTimeoutError and friends are retryable per the docstring contract."""
    from botocore.exceptions import ConnectTimeoutError, EndpointConnectionError, ReadTimeoutError

    assert _is_retryable_bedrock(ReadTimeoutError(endpoint_url="x")) is True
    assert _is_retryable_bedrock(ConnectTimeoutError(endpoint_url="x")) is True
    assert _is_retryable_bedrock(EndpointConnectionError(endpoint_url="x")) is True


def test_is_retryable_bedrock_unknown_exception_not_retryable() -> None:
    """An unknown error type is conservatively classified non-retryable."""
    assert _is_retryable_bedrock(RuntimeError("???")) is False


# --- backoff ---------------------------------------------------------


def test_backoff_delay_within_cap() -> None:
    for attempt in range(10):
        d = _backoff_delay(attempt)
        assert 0 <= d <= 60.0
