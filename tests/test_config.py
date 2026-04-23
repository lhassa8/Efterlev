"""Config round-trip + validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from efterlev.config import (
    DEFAULT_ANTHROPIC_MODEL,
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
    assert cfg.llm.model == DEFAULT_ANTHROPIC_MODEL
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
