# SPEC-11: LLMConfig.backend / region config surface

**Status:** implemented 2026-04-24
**Gate:** A3
**Depends on:** none (amends existing `LLMConfig` in `src/efterlev/config.py`)
**Blocks:** SPEC-10 (factory dispatch reads these fields — unblocked)
**Size:** S

## Goal

Tighten `LLMConfig.backend` from `str` to a `Literal` enum and add a conditional `region` field, so Efterlev configs declare their LLM backend unambiguously and Bedrock deployments carry the region they target. The change is backwards-compatible with existing `backend = "anthropic"` configs.

## Scope

- `LLMConfig.backend`: `str` → `Literal["anthropic", "bedrock"]`. Default `"anthropic"` unchanged.
- `LLMConfig.region`: new `str | None = None` field.
- Pydantic `model_validator(mode="after")` enforces:
  - `region` is required (non-None, non-empty) when `backend == "bedrock"`.
  - `region` is forbidden (must be None) when `backend == "anthropic"`.
- `efterlev init` writes `region = ""` (empty sentinel) only when the user chose Bedrock, matching the existing empty-string convention used for `fallback_model`.
- Error messages are user-grade: "LLMConfig.region is required when backend is 'bedrock'; set region to e.g. 'us-gov-west-1' or 'us-east-1'."

## Non-goals

- Backend-specific sub-sections (`[llm.bedrock]` table in config). One flat `[llm]` section stays the shape; backend-specific fields gated at the validator.
- Auto-detecting the region from AWS environment or instance-metadata. Explicit config beats implicit.
- Per-agent backend override (Gap on Bedrock, Documentation on Anthropic-direct). Single backend per config at v0.1.0; split if customer-pulled.
- Runtime backend switching in the same process. Config is loaded once.

## Interface

`src/efterlev/config.py` LLMConfig surface after this spec:

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, model_validator

class LLMConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: Literal["anthropic", "bedrock"] = "anthropic"
    model: str = DEFAULT_ANTHROPIC_MODEL
    fallback_model: str = DEFAULT_FALLBACK_MODEL
    region: str | None = None

    @model_validator(mode="after")
    def _region_required_iff_bedrock(self) -> "LLMConfig":
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
        return self
```

Config TOML shape:

```toml
# Commercial Anthropic-direct (default)
[llm]
backend = "anthropic"
model = "claude-opus-4-7"
fallback_model = "claude-sonnet-4-6"

# AWS Bedrock (commercial)
[llm]
backend = "bedrock"
model = "us.anthropic.claude-opus-4-7-v1:0"
region = "us-east-1"
fallback_model = "us.anthropic.claude-sonnet-4-6-v1:0"

# AWS Bedrock (GovCloud)
[llm]
backend = "bedrock"
model = "us.anthropic.claude-opus-4-7-v1:0"
region = "us-gov-west-1"
fallback_model = "us.anthropic.claude-sonnet-4-6-v1:0"
```

`efterlev init` surface (new optional flag):

```bash
efterlev init                                  # defaults to backend=anthropic
efterlev init --llm-backend bedrock \
              --llm-region us-gov-west-1 \
              --llm-model us.anthropic.claude-opus-4-7-v1:0
```

When `--llm-backend=bedrock` is given, `--llm-region` is required (Typer-level validation so the user sees the error immediately, not after the config round-trips through Pydantic).

## Behavior

- Existing `backend = "anthropic"` configs load unchanged.
- Existing configs with stray `region = "..."` lines alongside `backend = "anthropic"` now fail to load with the clear error message above. Expected failure; previously-accepted nonsense is caught.
- `efterlev init --llm-backend bedrock` without `--llm-region` fails at the Typer layer with a clear prompt to supply region.
- Config-file dump (the `render_config_toml` helper in `config.py`) emits `region = "..."` only when backend is bedrock; skips the line for anthropic to keep the default config visually clean.
- `pydantic.ValidationError` raised at config-load time (not at first LLM call) — fail fast.

## Data / schema

- Field-level addition to `LLMConfig`. Pydantic `extra="forbid"` already in place prevents users from setting unknown fields silently.
- No on-disk migration of existing `.efterlev/config.toml` files — pure field addition with a default.

## Test plan

- **Unit:**
  - `LLMConfig(backend="anthropic")` — OK, region is None
  - `LLMConfig(backend="bedrock", region="us-east-1")` — OK
  - `LLMConfig(backend="bedrock")` — ValidationError, message mentions "region is required"
  - `LLMConfig(backend="bedrock", region="")` — ValidationError (empty string fails the `not self.region` test)
  - `LLMConfig(backend="anthropic", region="us-east-1")` — ValidationError, message mentions "region must be unset"
  - `LLMConfig(backend="oracle")` — ValidationError (not in Literal set)
- **Integration:**
  - `efterlev init --llm-backend bedrock --llm-region us-gov-west-1` writes a valid config that subsequently loads.
  - `efterlev init --llm-backend bedrock` (no region) fails at Typer layer with a clear message.
- **Round-trip:** a generated bedrock config loads, serializes via `render_config_toml`, reloads, equals original.

## Exit criterion

- [x] `LLMConfig` in `src/efterlev/config.py` matches the Interface section above — `backend: Literal["anthropic", "bedrock"]`, new `region: str | None`, `model_validator` enforcing the either-or constraint.
- [x] `efterlev init` accepts `--llm-backend`, `--llm-region`, `--llm-model` flags with Typer-level validation (region required when bedrock; region forbidden when anthropic; unknown backend rejected).
- [x] `save_config` conditionally emits the region line only when backend=bedrock.
- [x] 9 new unit tests in `tests/test_config.py` covering: default shape, bedrock-requires-region, empty-string region rejected, GovCloud region accepted, commercial region accepted, anthropic forbids region, unknown backend rejected, TOML round-trip with bedrock, TOML skip-region-line with anthropic.
- [x] CLI smoke tested end-to-end on a fresh temp dir: anthropic default init → config with no region line; bedrock init → config with `region = "us-gov-west-1"`; bedrock without region → exit code 2 with clear error.
- [x] Existing tests for `LLMConfig` and `Config` pass unchanged. Total 469 tests pass.

## Risks

- **Users have custom config files with `region` already set for non-Bedrock backends.** Unlikely since the field didn't exist; if anyone scripted a prospective config, the error message tells them what to do.
- **Pydantic validator runs before `model_config`'s frozen check, so error message quality matters.** Mitigation: the Interface section above has tested message text.

## Open questions

None.
