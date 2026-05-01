"""`efterlev doctor` — self-diagnose pre-flight checks.

Priority 3 (2026-04-28). On a fresh install, the most-common failure
mode is "agent invocation explodes because ANTHROPIC_API_KEY is unset"
or "FRMR cache is missing because init wasn't run." Both produce
unfriendly tracebacks. `efterlev doctor` runs a series of cheap checks
and reports per-check pass/fail with remediation pointers, so users
catch the misconfiguration before the first agent run.

Checks are pure functions that return a `Check` dataclass. The
top-level `run_doctor_checks(target)` aggregates them. The CLI command
in `cli/main.py` wires it to typer and exits non-zero if any required
check fails.

Network reachability checks are intentionally NOT included — they're
flaky in CI sandboxes, add latency, and add a network dependency to a
diagnostic tool. The doctor inspects local state only.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

CheckStatus = Literal["pass", "warn", "fail"]


@dataclass(frozen=True)
class Check:
    """One diagnostic check's outcome.

    `severity`: a "fail" indicates the user can't run the agent
    pipeline — exit non-zero. A "warn" is a heads-up (e.g. Bedrock
    creds optional, FRMR cache slightly stale). A "pass" is the green
    case.
    """

    name: str
    status: CheckStatus
    detail: str
    hint: str | None = None


# Minimum supported Python — matches pyproject.toml's `requires-python`.
_MIN_PYTHON = (3, 10)


def check_python_version() -> Check:
    if sys.version_info[:2] >= _MIN_PYTHON:
        return Check(
            name="python_version",
            status="pass",
            detail=f"Python {sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}",
        )
    cur_v = f"{sys.version_info[0]}.{sys.version_info[1]}"
    min_v = f"{_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}"
    return Check(
        name="python_version",
        status="fail",
        detail=f"Python {cur_v} is below required {min_v}",
        hint="Upgrade Python to 3.10 or newer (we recommend 3.12).",
    )


def check_anthropic_api_key(*, configured_backend: str | None = None) -> Check:
    """Check ANTHROPIC_API_KEY presence and shape.

    Skipped when the workspace's configured backend is `bedrock` —
    the key is irrelevant on that path and the warn was noise. The
    shape check is conservative: real keys start with `sk-ant-` and
    are 100+ chars. We don't make a network call to validate the key
    here — that's the bedrock-side InvokeModel ping or the Anthropic-
    side first agent call.
    """
    if configured_backend == "bedrock":
        return Check(
            name="anthropic_api_key",
            status="pass",
            detail="skipped — workspace is configured for the Bedrock backend",
        )
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return Check(
            name="anthropic_api_key",
            status="warn",
            detail="ANTHROPIC_API_KEY is not set in the environment",
            hint=(
                "Set ANTHROPIC_API_KEY before running any `efterlev agent` "
                "command. Get a key at https://console.anthropic.com. "
                "Bedrock users can skip this — see `[bedrock]` in config.toml."
            ),
        )
    if not key.startswith("sk-ant-"):
        return Check(
            name="anthropic_api_key",
            status="warn",
            detail=f"ANTHROPIC_API_KEY is set but doesn't start with 'sk-ant-' (length {len(key)})",
            hint=(
                "Real Anthropic API keys start with `sk-ant-`. The current "
                "value may be a Bedrock key or a leftover placeholder. "
                "Verify before running an agent."
            ),
        )
    return Check(
        name="anthropic_api_key",
        status="pass",
        detail=f"ANTHROPIC_API_KEY is set (sk-ant-…, length {len(key)})",
    )


def check_efterlev_dir(target: Path) -> Check:
    """Check whether `.efterlev/` exists in the target directory."""
    efterlev_dir = target / ".efterlev"
    if efterlev_dir.is_dir():
        return Check(
            name="efterlev_dir",
            status="pass",
            detail=f".efterlev/ found at {efterlev_dir}",
        )
    return Check(
        name="efterlev_dir",
        status="warn",
        detail=f"No .efterlev/ at {target} — workspace not initialized",
        hint="Run `efterlev init` in the workspace before scanning or invoking agents.",
    )


_FRMR_CACHE_REL = Path(".efterlev/cache/frmr_document.json")
# Stale threshold: 90 days. The FRMR catalog is vendored, so the cache
# is the canonical local copy — if it's older than this, the user is
# almost certainly running against an outdated FedRAMP standard.
_FRMR_STALE_SECONDS = 90 * 24 * 60 * 60


def check_frmr_cache(target: Path) -> Check:
    """Check the FRMR-cache file is present and not impossibly stale."""
    cache = target / _FRMR_CACHE_REL
    if not cache.is_file():
        return Check(
            name="frmr_cache",
            status="warn",
            detail=f"FRMR cache missing at {cache}",
            hint=(
                "Run `efterlev init` to populate the FRMR cache. The "
                "cache contains the vendored FedRAMP catalog; agents "
                "and `efterlev scan` need it."
            ),
        )
    age_seconds = time.time() - cache.stat().st_mtime
    if age_seconds > _FRMR_STALE_SECONDS:
        days = int(age_seconds / 86400)
        return Check(
            name="frmr_cache",
            status="warn",
            detail=f"FRMR cache at {cache} is {days} days old",
            hint=(
                "Re-run `efterlev init --force` to refresh the FRMR "
                "cache from the vendored catalog (which itself ships "
                "with the installed efterlev package)."
            ),
        )
    return Check(
        name="frmr_cache",
        status="pass",
        detail=f"FRMR cache at {cache}",
    )


def check_bedrock_credentials(
    *,
    configured_backend: str | None = None,
    configured_region: str | None = None,
    configured_model: str | None = None,
) -> Check:
    """Optional check: is the Bedrock LLM backend usable?

    Uses boto3's full credential resolution chain (env vars → shared
    credentials file → AWS_PROFILE → IMDS → SSO → container metadata),
    which is what the runtime actually consults. Earlier versions of
    this check only inspected env vars and false-warned on configs
    where `~/.aws/credentials` or an SSO session was already valid
    (real first-run report 2026-04-30).

    When `configured_backend == "bedrock"`, additionally validates the
    configured model end-to-end with a 1-token `InvokeModel` ping —
    catches stale defaults, missing inference profiles, expired creds,
    and access-denied scenarios in the diagnostic phase before users
    spend money on a doomed agent run. The ping is intentionally
    minimal (`max_tokens=1`, throwaway prompt) so the cost is fractions
    of a cent.
    """
    region = (
        configured_region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    )

    try:
        import boto3
        from botocore.exceptions import (  # type: ignore[import-untyped]
            BotoCoreError,
            ClientError,
            NoCredentialsError,
        )
    except ImportError:
        return Check(
            name="bedrock_credentials",
            status="warn",
            detail="boto3 not installed (Bedrock backend unavailable)",
            hint=(
                "If you don't use Bedrock, ignore this check. To install "
                "the Bedrock backend: `pipx install 'efterlev[bedrock]'` "
                "(or use the container image)."
            ),
        )

    # boto3's full credential chain — env, shared file, AWS_PROFILE,
    # IMDS, SSO, container creds. Matches what the runtime client uses.
    try:
        session = boto3.Session()
        creds = session.get_credentials()
    except Exception as e:  # pragma: no cover - boto3 setup edge cases
        return Check(
            name="bedrock_credentials",
            status="warn",
            detail=f"boto3 session init failed: {e}",
            hint="Check `aws configure` or your AWS_PROFILE / SSO setup.",
        )

    if creds is None:
        return Check(
            name="bedrock_credentials",
            status="warn",
            detail="No AWS credentials resolvable from any source (Bedrock backend unavailable)",
            hint=(
                "If you don't use Bedrock, ignore this check. To enable "
                "Bedrock: run `aws configure` (writes to ~/.aws/credentials), "
                "or set AWS_PROFILE, or export AWS_ACCESS_KEY_ID + "
                "AWS_SECRET_ACCESS_KEY. Then set [llm].backend = 'bedrock' "
                "in .efterlev/config.toml."
            ),
        )

    if not region:
        return Check(
            name="bedrock_credentials",
            status="warn",
            detail="AWS credentials resolved but no region configured",
            hint=(
                "Set AWS_REGION (or AWS_DEFAULT_REGION), or `aws configure "
                "set region us-east-1`, so Bedrock knows where to call. "
                "GovCloud customers: use `us-gov-west-1`."
            ),
        )

    # Skip the InvokeModel ping unless the workspace is actually configured
    # for Bedrock. On Anthropic-backend workspaces we just want to confirm
    # that Bedrock COULD be used without spending API budget.
    if configured_backend != "bedrock" or not configured_model:
        return Check(
            name="bedrock_credentials",
            status="pass",
            detail=(
                f"AWS credentials resolved + region {region} configured (Bedrock backend usable)"
            ),
        )

    # End-to-end ping: 1 token, throwaway prompt. Catches stale model
    # defaults, missing inference-profile access, and credential lifetimes
    # before the first agent run.
    try:
        from botocore.config import Config

        client = session.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(read_timeout=30, connect_timeout=10, retries={"max_attempts": 1}),
        )
        client.converse(
            modelId=configured_model,
            messages=[{"role": "user", "content": [{"text": "ping"}]}],
            inferenceConfig={"maxTokens": 1},
        )
    except NoCredentialsError:
        return Check(
            name="bedrock_credentials",
            status="fail",
            detail="boto3 reported credentials, but Bedrock rejected them",
            hint="Refresh credentials (e.g. `aws sso login`) and re-run.",
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "?")
        msg = e.response.get("Error", {}).get("Message", str(e))
        if code in ("AccessDeniedException", "UnauthorizedException"):
            return Check(
                name="bedrock_credentials",
                status="fail",
                detail=f"Bedrock denied access to {configured_model}: {msg}",
                hint=(
                    "Request access to the model in the Bedrock console "
                    "(console.aws.amazon.com/bedrock → Model access), or "
                    "pick a different `model` in .efterlev/config.toml."
                ),
            )
        if code in ("ResourceNotFoundException", "ValidationException"):
            return Check(
                name="bedrock_credentials",
                status="fail",
                detail=f"Configured model {configured_model!r} is not callable: {msg}",
                hint=(
                    "Run `aws bedrock list-inference-profiles --type-equals "
                    "SYSTEM_DEFINED --region <region>` and pick a current "
                    "Anthropic profile ARN. Update [llm].model in "
                    ".efterlev/config.toml."
                ),
            )
        # Throttling / 5xx — credentials and model are fine, just a transient
        return Check(
            name="bedrock_credentials",
            status="warn",
            detail=f"Bedrock ping returned {code}: {msg}",
            hint="Retry in a moment; credentials and model look OK.",
        )
    except BotoCoreError as e:
        return Check(
            name="bedrock_credentials",
            status="warn",
            detail=f"Bedrock ping connection error: {e}",
            hint="Network reachability to Bedrock failed; check VPC endpoints / proxy config.",
        )

    return Check(
        name="bedrock_credentials",
        status="pass",
        detail=(
            f"InvokeModel ping succeeded against {configured_model} in {region} "
            "(creds + model verified end-to-end)"
        ),
    )


def _read_configured_backend(target: Path) -> tuple[str | None, str | None, str | None]:
    """Best-effort read of `[llm]` settings from `.efterlev/config.toml`.

    Returns (backend, region, model) — any missing field is None. Failures
    parsing the file return all-None silently; the doctor checks fall back
    to env-var inspection in that case.
    """
    config_path = target / ".efterlev" / "config.toml"
    if not config_path.is_file():
        return (None, None, None)
    try:
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return (None, None, None)
    llm = data.get("llm", {}) if isinstance(data, dict) else {}
    if not isinstance(llm, dict):
        return (None, None, None)
    backend = llm.get("backend") if isinstance(llm.get("backend"), str) else None
    region = llm.get("region") if isinstance(llm.get("region"), str) else None
    model = llm.get("model") if isinstance(llm.get("model"), str) else None
    return (backend, region, model)


def run_doctor_checks(target: Path) -> list[Check]:
    """Run every doctor check and return the results in display order.

    Order: Python (foundational), .efterlev workspace state, FRMR cache
    (init artifact), API keys (agent invocation), Bedrock (optional).

    The api-key and bedrock checks are config-aware: if `.efterlev/
    config.toml` declares `backend = "bedrock"`, the anthropic-key
    check skips, and the bedrock check additionally pings InvokeModel
    against the configured model (1-token round-trip).
    """
    backend, region, model = _read_configured_backend(target)
    return [
        check_python_version(),
        check_efterlev_dir(target),
        check_frmr_cache(target),
        check_anthropic_api_key(configured_backend=backend),
        check_bedrock_credentials(
            configured_backend=backend,
            configured_region=region,
            configured_model=model,
        ),
    ]


def has_failures(checks: list[Check]) -> bool:
    """True if any check is `fail` (the gate for non-zero exit). Warns
    don't block — they're informational."""
    return any(c.status == "fail" for c in checks)
