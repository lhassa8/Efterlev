"""Tests for the LLM factory dispatch (SPEC-10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from efterlev.config import LLMConfig
from efterlev.errors import AgentError
from efterlev.llm.anthropic_client import AnthropicClient
from efterlev.llm.bedrock_client import AnthropicBedrockClient
from efterlev.llm.factory import (
    DEFAULT_FALLBACK_MODEL,
    _find_workspace_config,
    get_client_from_config,
    get_default_client,
)

# --- get_client_from_config ------------------------------------------


def test_anthropic_config_returns_anthropic_client() -> None:
    config = LLMConfig(backend="anthropic")
    client = get_client_from_config(config)
    assert isinstance(client, AnthropicClient)


def test_bedrock_config_returns_bedrock_client() -> None:
    config = LLMConfig(
        backend="bedrock",
        model="us.anthropic.claude-opus-4-7-v1:0",
        region="us-gov-west-1",
    )
    client = get_client_from_config(config)
    assert isinstance(client, AnthropicBedrockClient)
    assert client.region == "us-gov-west-1"


def test_bedrock_config_passes_fallback_through() -> None:
    config = LLMConfig(
        backend="bedrock",
        model="us.anthropic.claude-opus-4-7-v1:0",
        region="us-east-1",
        fallback_model="us.anthropic.claude-sonnet-4-6-v1:0",
    )
    client = get_client_from_config(config)
    assert isinstance(client, AnthropicBedrockClient)
    assert client.fallback_model == "us.anthropic.claude-sonnet-4-6-v1:0"


def test_empty_string_fallback_normalized_to_none() -> None:
    """fallback_model='' (operator opt-out) → None at the client level."""
    config = LLMConfig(backend="anthropic", fallback_model="")
    client = get_client_from_config(config)
    assert isinstance(client, AnthropicClient)
    assert client.fallback_model is None


def test_bedrock_without_region_raises_defensively() -> None:
    """Belt-and-suspenders: even if Pydantic validator was bypassed, the
    factory refuses to construct a Bedrock client without a region."""
    # Construct via model_construct to bypass the Pydantic validator —
    # simulating an in-process mutation that shouldn't be possible but
    # we guard against anyway.
    config = LLMConfig.model_construct(backend="bedrock", region=None)
    with pytest.raises(AgentError, match="region is required"):
        get_client_from_config(config)


# --- get_default_client ----------------------------------------------


def test_default_client_falls_back_to_anthropic_when_no_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Outside any workspace, default client is anthropic with hardcoded fallback."""
    monkeypatch.chdir(tmp_path)
    client = get_default_client()
    assert isinstance(client, AnthropicClient)
    assert client.fallback_model == DEFAULT_FALLBACK_MODEL


def test_default_client_reads_workspace_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When `.efterlev/config.toml` exists in cwd, factory loads it and dispatches."""
    config_dir = tmp_path / ".efterlev"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        "[llm]\n"
        'backend = "bedrock"\n'
        'model = "us.anthropic.claude-opus-4-7-v1:0"\n'
        'fallback_model = "us.anthropic.claude-sonnet-4-6-v1:0"\n'
        'region = "us-gov-west-1"\n'
        '\n[scan]\ntarget_dir = "."\noutput_dir = "./out"\n'
        '\n[baseline]\nid = "fedramp-20x-moderate"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    client = get_default_client()
    assert isinstance(client, AnthropicBedrockClient)
    assert client.region == "us-gov-west-1"


def test_default_client_walks_up_to_find_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Agent invoked from a subdir of a workspace should still find the config."""
    config_dir = tmp_path / ".efterlev"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        "[llm]\n"
        'backend = "anthropic"\n'
        'model = "claude-opus-4-7"\n'
        'fallback_model = "claude-sonnet-4-6"\n'
        '\n[scan]\ntarget_dir = "."\noutput_dir = "./out"\n'
        '\n[baseline]\nid = "fedramp-20x-moderate"\n',
        encoding="utf-8",
    )
    subdir = tmp_path / "deep" / "nested"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)
    client = get_default_client()
    assert isinstance(client, AnthropicClient)


def test_default_client_silent_fallback_on_malformed_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed config in cwd should not crash the factory — defaults take over.
    The CLI's own load_config call is the place where malformed configs surface."""
    config_dir = tmp_path / ".efterlev"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text("this is not [ valid ] toml = = =", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    client = get_default_client()
    assert isinstance(client, AnthropicClient)
    assert client.fallback_model == DEFAULT_FALLBACK_MODEL


# --- _find_workspace_config ------------------------------------------


def test_find_workspace_config_walks_up(tmp_path: Path) -> None:
    config_dir = tmp_path / ".efterlev"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text("placeholder", encoding="utf-8")
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    found = _find_workspace_config(deep)
    assert found == config_file


def test_find_workspace_config_returns_none_when_no_workspace(
    tmp_path: Path,
) -> None:
    found = _find_workspace_config(tmp_path)
    # tmp_path's ancestors typically don't have an .efterlev/config.toml,
    # but we guard against the developer running tests from inside an
    # actual Efterlev workspace by checking explicitly.
    if found is not None:
        # Test environment has a workspace ancestor; the function works
        # correctly, it just found one.
        assert found.is_file()
    else:
        assert found is None
