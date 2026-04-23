"""`.efterlev/config.toml` schema + read/write helpers.

v0 config is small: which baseline was selected, which LLM backend and model
to use, and where `efterlev scan` writes output. The Pydantic schema is
conservative — only fields that actually do something land here, per
CLAUDE.md's "keep it small; don't include settings that don't yet do
anything." Adding a field is a deliberate decision that lands with the code
that reads it.

Format: TOML. Read via stdlib `tomllib`; written via a small hand-rolled
formatter because Python's stdlib doesn't ship a TOML writer.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from efterlev.errors import ConfigError

DEFAULT_BASELINE = "fedramp-20x-moderate"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-7"
DEFAULT_FALLBACK_MODEL = "claude-sonnet-4-6"


class LLMConfig(BaseModel):
    """Which LLM endpoint and model the generative agents call.

    `fallback_model` returned 2026-04-23 with the retry+fallback
    implementation in `llm.anthropic_client`. When the primary `model`
    fails three transient-retry attempts, `AnthropicClient` tries the
    fallback once before surfacing the error. Set to empty string
    (`fallback_model = ""`) to disable fallback entirely — useful when
    the deployment wants a single model identity in every provenance
    record.

    Retry counts live as in-class constants in `anthropic_client.py`
    rather than in config, per the "keep it small" policy. If real-
    world operations reveal they need per-deployment tuning, they
    promote to config at that time.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: str = "anthropic"
    model: str = DEFAULT_ANTHROPIC_MODEL
    fallback_model: str = DEFAULT_FALLBACK_MODEL


class ScanConfig(BaseModel):
    """Where `efterlev scan` reads from and writes to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_dir: str = "."
    output_dir: str = "./out"


class BaselineConfig(BaseModel):
    """Which compliance baseline this workspace was initialized against."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = DEFAULT_BASELINE


class Config(BaseModel):
    """Top-level `.efterlev/config.toml` schema."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    llm: LLMConfig = Field(default_factory=LLMConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    baseline: BaselineConfig = Field(default_factory=BaselineConfig)


def load_config(path: Path) -> Config:
    """Read and parse `.efterlev/config.toml`; raise `ConfigError` on malformed input."""
    if not path.is_file():
        raise ConfigError(f"config not found at {path}")
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"config at {path} is not valid TOML: {e}") from e
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"config at {path} does not match schema: {e}") from e


def save_config(config: Config, path: Path) -> None:
    """Write `config` as TOML to `path`. Creates parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Efterlev workspace config — written by `efterlev init`.",
        "# Edit freely; `efterlev` commands read this on every invocation.",
        "",
        "[llm]",
        f'backend = "{config.llm.backend}"',
        f'model = "{config.llm.model}"',
        f'fallback_model = "{config.llm.fallback_model}"',
        "",
        "[scan]",
        f'target_dir = "{config.scan.target_dir}"',
        f'output_dir = "{config.scan.output_dir}"',
        "",
        "[baseline]",
        f'id = "{config.baseline.id}"',
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
