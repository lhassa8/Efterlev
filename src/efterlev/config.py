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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from efterlev.errors import ConfigError

DEFAULT_BASELINE = "fedramp-20x-moderate"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-7"
DEFAULT_FALLBACK_MODEL = "claude-sonnet-4-6"
# Bedrock-shaped model ID for the Bedrock backend. The Anthropic short-form
# IDs the per-agent default_model values use (e.g. "claude-opus-4-7") are
# not valid Bedrock model identifiers, so the Bedrock backend always
# populates LLMConfig.model — None cannot fall through to the per-agent
# default the way it does for the Anthropic backend.
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-opus-4-7-v1:0"


class LLMConfig(BaseModel):
    """Which LLM endpoint and model the generative agents call.

    `fallback_model` returned 2026-04-23 with the retry+fallback
    implementation in `llm.anthropic_client`. When the primary `model`
    fails three transient-retry attempts, `AnthropicClient` tries the
    fallback once before surfacing the error. Set to empty string
    (`fallback_model = ""`) to disable fallback entirely — useful when
    the deployment wants a single model identity in every provenance
    record.

    `backend` and `region` landed 2026-04-24 as part of SPEC-11. The
    Bedrock backend (SPEC-10) is required by the open-source launch
    posture to make GovCloud EC2 deployments possible without egress
    to anthropic.com. `region` is conditional: required when
    `backend == "bedrock"`, forbidden when `backend == "anthropic"`.
    The validator enforces the either-or at config-load time so
    misconfigured deployments fail fast rather than at first LLM call.

    Retry counts live as in-class constants in `anthropic_client.py`
    rather than in config, per the "keep it small" policy. If real-
    world operations reveal they need per-deployment tuning, they
    promote to config at that time.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: Literal["anthropic", "bedrock"] = "anthropic"
    # `model` is the user's project-level model preference. None means
    # "use the agent's per-task default" — DocumentationAgent picks
    # Sonnet 4.6 for cost; Gap and Remediation pick Opus 4.7 for
    # reasoning quality. A non-None value overrides every agent's
    # default uniformly. Init writes None when the user does not pass
    # `--llm-model`, so the per-agent defaults stay live unless the
    # user explicitly opts into a single project-wide model.
    # Bedrock backend always populates this with a Bedrock-shaped
    # model ID (the Anthropic short-form IDs that the per-agent
    # defaults use are not valid Bedrock model identifiers).
    model: str | None = None
    fallback_model: str = DEFAULT_FALLBACK_MODEL
    region: str | None = None

    @model_validator(mode="after")
    def _region_required_iff_bedrock(self) -> LLMConfig:
        if self.backend == "bedrock" and not self.region:
            raise ValueError(
                "LLMConfig.region is required when backend is 'bedrock'; "
                "set region to e.g. 'us-gov-west-1' or 'us-east-1'."
            )
        if self.backend == "anthropic" and self.region is not None:
            raise ValueError(
                "LLMConfig.region must be unset when backend is 'anthropic' "
                "(region is only used by the Bedrock backend)."
            )
        if self.backend == "bedrock" and self.model is None:
            raise ValueError(
                "LLMConfig.model is required when backend is 'bedrock'; "
                "Bedrock model IDs differ from the Anthropic short-form IDs "
                f"the agent defaults use (e.g. '{DEFAULT_BEDROCK_MODEL}')."
            )
        return self


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
    llm_lines = [
        "[llm]",
        f'backend = "{config.llm.backend}"',
    ]
    # Skip the `model` line when None — pydantic accepts a missing field via
    # the LLMConfig.model default, and writing `model = "None"` would be
    # interpreted as a literal string "None" by tomllib on the next load.
    # None means "use the agent's per-task default"; the absence of the line
    # is the canonical encoding of that intent.
    if config.llm.model is not None:
        llm_lines.append(f'model = "{config.llm.model}"')
    llm_lines.append(f'fallback_model = "{config.llm.fallback_model}"')
    # SPEC-11: emit region only when backend=bedrock to keep the default
    # (anthropic) config visually minimal. Pydantic validator guarantees
    # region is set iff backend==bedrock.
    if config.llm.backend == "bedrock":
        llm_lines.append(f'region = "{config.llm.region}"')
    lines = [
        "# Efterlev workspace config — written by `efterlev init`.",
        "# Edit freely; `efterlev` commands read this on every invocation.",
        "",
        *llm_lines,
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
