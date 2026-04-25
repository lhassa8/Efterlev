"""Default LLM client factory.

`get_default_client()` is the entry point for agents. It looks for
`.efterlev/config.toml` in cwd; if found, dispatches on the configured
backend (`anthropic` or `bedrock` per SPEC-11). If not found, falls
back to hard-coded anthropic defaults — preserving v0 behavior for
tests and one-off scripts that don't have a workspace.

`get_client_from_config(llm_config)` is the explicit-config variant for
callers that have already loaded their config (typical CLI path).

Fallback-model selection: when the config has a non-empty
`fallback_model`, both backends try it once after primary-model retries
are exhausted before surfacing the error. Set `fallback_model = ""` in
config to disable.
"""

from __future__ import annotations

from pathlib import Path

from efterlev.config import LLMConfig, load_config
from efterlev.errors import AgentError, ConfigError
from efterlev.llm.anthropic_client import AnthropicClient
from efterlev.llm.base import LLMClient
from efterlev.llm.bedrock_client import AnthropicBedrockClient

# CLAUDE.md: default model is claude-opus-4-7; switch to sonnet only for
# latency during demo. Agents can override per-call, but the default lives
# here so changing it is a one-line edit.
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_FALLBACK_MODEL = "claude-sonnet-4-6"


def get_client_from_config(llm_config: LLMConfig) -> LLMClient:
    """Construct an `LLMClient` matching the supplied config.

    Dispatches on `llm_config.backend`. The Pydantic validator on
    `LLMConfig` guarantees the backend/region invariants, so we don't
    re-check them here beyond what's needed for a clear error.
    """
    fallback = llm_config.fallback_model or None
    if llm_config.backend == "bedrock":
        if not llm_config.region:
            # The validator should have caught this, but defense in depth:
            # never construct a Bedrock client without a region.
            raise AgentError(
                "LLMConfig.region is required for backend='bedrock' "
                "but was unset; check `.efterlev/config.toml`."
            )
        return AnthropicBedrockClient(
            region=llm_config.region,
            fallback_model=fallback,
        )
    return AnthropicClient(fallback_model=fallback)


def get_default_client() -> LLMClient:
    """Return the default LLM client.

    Reads `.efterlev/config.toml` from cwd (or the closest ancestor)
    and dispatches on backend. Falls back to anthropic-with-Sonnet-fallback
    defaults when no config file is reachable — preserves v0 behavior
    for ad-hoc scripts and unit tests.
    """
    config_path = _find_workspace_config(Path.cwd())
    if config_path is not None:
        try:
            config = load_config(config_path)
            return get_client_from_config(config.llm)
        except ConfigError:
            # Malformed config under a workspace dir is a real bug worth
            # surfacing — but the LLM factory isn't the right place to do
            # that. Fall back to defaults silently here; the CLI will
            # surface the malformed config when it runs `load_config`
            # directly elsewhere.
            pass
    return AnthropicClient(fallback_model=DEFAULT_FALLBACK_MODEL)


def _find_workspace_config(start: Path) -> Path | None:
    """Walk up from `start` looking for a `.efterlev/config.toml`.

    Returns the first one found, or None if we hit the filesystem root.
    The walk lets agents work from anywhere inside a workspace, not just
    its root — matching how `git` and similar dev tools resolve their
    config.
    """
    current = start.resolve()
    while True:
        candidate = current / ".efterlev" / "config.toml"
        if candidate.is_file():
            return candidate
        if current.parent == current:
            return None
        current = current.parent
