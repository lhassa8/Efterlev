"""Config round-trip + validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from efterlev.config import (
    BaselineConfig,
    Config,
    LLMConfig,
    ScanConfig,
    load_config,
    save_config,
)
from efterlev.errors import ConfigError


def test_defaults_are_efterlev_v0_expectations() -> None:
    cfg = Config()
    assert cfg.llm.backend == "anthropic"
    # `model` defaults to None — the canonical "use the agent's per-task
    # default" sentinel. DocumentationAgent picks Sonnet for cost; Gap and
    # Remediation pick Opus for reasoning. A non-None value overrides every
    # agent's default uniformly.
    assert cfg.llm.model is None
    assert cfg.scan.target_dir == "."
    assert cfg.scan.output_dir == "./out"
    assert cfg.baseline.id == "fedramp-20x-moderate"


def test_round_trip_through_toml(tmp_path: Path) -> None:
    cfg = Config(
        llm=LLMConfig(backend="anthropic", model="claude-opus-4-7"),
        scan=ScanConfig(target_dir="./src", output_dir="./out/v1"),
        baseline=BaselineConfig(id="fedramp-20x-moderate"),
    )
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    restored = load_config(path)
    assert restored == cfg


def test_load_missing_config_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "does-not-exist.toml")


def test_load_malformed_toml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("this is [ not valid ] toml = = =")
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_config(bad)


def test_unknown_fields_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        "[llm]\n"
        'backend = "anthropic"\n'
        'model = "claude-opus-4-7"\n'
        'nonsense_field = "oops"\n'
        "\n[scan]\n"
        'target_dir = "."\n'
        'output_dir = "./out"\n'
        "\n[baseline]\n"
        'id = "fedramp-20x-moderate"\n'
    )
    with pytest.raises(ConfigError, match="does not match schema"):
        load_config(bad)


def test_config_accepts_fallback_model(tmp_path: Path) -> None:
    """The `fallback_model` field returned 2026-04-23 paired with the
    retry+fallback implementation. Loading a config that sets it should
    succeed and round-trip."""
    toml = tmp_path / "with_fallback.toml"
    toml.write_text(
        "[llm]\n"
        'backend = "anthropic"\n'
        'model = "claude-opus-4-7"\n'
        'fallback_model = "claude-sonnet-4-6"\n'
        "\n[scan]\n"
        'target_dir = "."\n'
        'output_dir = "./out"\n'
        "\n[baseline]\n"
        'id = "fedramp-20x-moderate"\n'
    )
    config = load_config(toml)
    assert config.llm.fallback_model == "claude-sonnet-4-6"


def test_config_default_fallback_model_is_sonnet(tmp_path: Path) -> None:
    """A config that omits `fallback_model` picks up the default Sonnet —
    fallback is on by default, not opt-in. An operator who wants to disable
    it sets an empty string (documented in the LLMConfig docstring)."""
    from efterlev.config import DEFAULT_FALLBACK_MODEL, LLMConfig

    cfg = LLMConfig()
    assert cfg.fallback_model == DEFAULT_FALLBACK_MODEL


# --- SPEC-11: backend/region validator --------------------------------


def test_llm_config_default_is_anthropic_with_no_region() -> None:
    cfg = LLMConfig()
    assert cfg.backend == "anthropic"
    assert cfg.region is None


def test_llm_config_bedrock_requires_region() -> None:
    """SPEC-11: backend=bedrock without region is a config-time error,
    not a runtime error at first LLM call."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="region is required"):
        LLMConfig(backend="bedrock")


def test_llm_config_bedrock_empty_string_region_rejected() -> None:
    """Empty string is not a valid region — falsy truthiness catches it."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="region is required"):
        LLMConfig(backend="bedrock", region="")


def test_llm_config_bedrock_accepts_govcloud_region() -> None:
    cfg = LLMConfig(
        backend="bedrock",
        model="us.anthropic.claude-opus-4-7-v1:0",
        region="us-gov-west-1",
    )
    assert cfg.backend == "bedrock"
    assert cfg.region == "us-gov-west-1"


def test_llm_config_bedrock_accepts_commercial_region() -> None:
    cfg = LLMConfig(
        backend="bedrock",
        model="us.anthropic.claude-opus-4-7-v1:0",
        region="us-east-1",
    )
    assert cfg.region == "us-east-1"


def test_llm_config_anthropic_forbids_region() -> None:
    """Setting region alongside backend=anthropic is a misconfiguration
    that previously would have been silently accepted."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="region must be unset"):
        LLMConfig(backend="anthropic", region="us-east-1")


def test_llm_config_rejects_unknown_backend() -> None:
    """Literal narrows backend to 'anthropic' | 'bedrock'; anything else
    fails at Pydantic's type level before the model_validator runs."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LLMConfig(backend="oracle")  # type: ignore[arg-type]


def test_config_toml_round_trip_with_bedrock(tmp_path: Path) -> None:
    """A Bedrock config round-trips through TOML preserving region."""
    cfg = Config(
        llm=LLMConfig(
            backend="bedrock",
            model="us.anthropic.claude-opus-4-7-v1:0",
            region="us-gov-west-1",
        ),
    )
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    restored = load_config(path)
    assert restored == cfg
    # And the saved TOML actually contains the region line.
    assert 'region = "us-gov-west-1"' in path.read_text()


def test_config_toml_anthropic_omits_region_line(tmp_path: Path) -> None:
    """Default (anthropic) config should not emit a region line — keeps
    the common-case config visually minimal."""
    cfg = Config()
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    assert "region" not in path.read_text()


# --- model: None sentinel + wire-through ---------------------------------


def test_save_config_omits_model_line_when_none(tmp_path: Path) -> None:
    """`model = None` is the canonical "use the agent's per-task default"
    sentinel. Writing `model = "None"` would round-trip as a literal string
    and silently override every agent with a nonsense identifier; instead
    save_config omits the line entirely."""
    cfg = Config()  # model=None by default
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    text = path.read_text()
    # No `model = "..."` line; `fallback_model` still appears so a substring
    # check on "model" is too broad — check the specific assignment instead.
    assert "\nmodel = " not in text
    # Round-trip preserves None.
    restored = load_config(path)
    assert restored.llm.model is None


def test_load_config_accepts_missing_model_line(tmp_path: Path) -> None:
    """A hand-edited config without a `model` line should load cleanly
    and set llm.model to None — the per-agent default applies at runtime."""
    toml = tmp_path / "no_model.toml"
    toml.write_text(
        "[llm]\n"
        'backend = "anthropic"\n'
        'fallback_model = "claude-sonnet-4-6"\n'
        "\n[scan]\n"
        'target_dir = "."\n'
        'output_dir = "./out"\n'
        "\n[baseline]\n"
        'id = "fedramp-20x-moderate"\n'
    )
    config = load_config(toml)
    assert config.llm.model is None


def test_llm_config_bedrock_rejects_none_model() -> None:
    """SPEC-11 + 2026-04-26 wire-through: Bedrock model IDs differ from the
    Anthropic short-form IDs the agent default_model values use, so None
    cannot fall through to the per-agent default for Bedrock backends.
    Init enforces this by writing a Bedrock-shaped ID; the validator is
    the defense in depth."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="model is required when backend is 'bedrock'"):
        LLMConfig(backend="bedrock", model=None, region="us-gov-west-1")


def test_configured_model_flows_to_agent(tmp_path: Path) -> None:
    """End-to-end wire-through: an explicit `model` in the loaded config
    must reach the agent's `self.model`. Before this test, --llm-model at
    init was dead config (configured but never read by agent runtime)."""
    from efterlev.agents import DocumentationAgent, GapAgent, RemediationAgent
    from efterlev.llm import StubLLMClient

    toml = tmp_path / "configured.toml"
    toml.write_text(
        "[llm]\n"
        'backend = "anthropic"\n'
        'model = "claude-haiku-4-5"\n'
        'fallback_model = "claude-sonnet-4-6"\n'
        "\n[scan]\n"
        'target_dir = "."\n'
        'output_dir = "./out"\n'
        "\n[baseline]\n"
        'id = "fedramp-20x-moderate"\n'
    )
    cfg = load_config(toml)
    assert cfg.llm.model == "claude-haiku-4-5"
    stub = StubLLMClient(response_text="{}")
    assert GapAgent(client=stub, model=cfg.llm.model).model == "claude-haiku-4-5"
    assert DocumentationAgent(client=stub, model=cfg.llm.model).model == "claude-haiku-4-5"
    assert RemediationAgent(client=stub, model=cfg.llm.model).model == "claude-haiku-4-5"


def test_unconfigured_model_falls_through_to_agent_default(tmp_path: Path) -> None:
    """When the user does not pass --llm-model at init, config.llm.model is
    None and each agent uses its own default — Sonnet for Documentation
    (cost-saving), Opus for Gap and Remediation (reasoning quality)."""
    from efterlev.agents import DocumentationAgent, GapAgent, RemediationAgent
    from efterlev.llm import StubLLMClient

    cfg = Config()  # default — model=None
    stub = StubLLMClient(response_text="{}")
    assert cfg.llm.model is None
    assert GapAgent(client=stub, model=cfg.llm.model).model == "claude-opus-4-7"
    assert DocumentationAgent(client=stub, model=cfg.llm.model).model == "claude-sonnet-4-6"
    assert RemediationAgent(client=stub, model=cfg.llm.model).model == "claude-opus-4-7"
