"""Friendly error formatting for LLM/credential failures at CLI boundary.

Priority 3.2 (2026-04-28). Without this layer, a missing
`ANTHROPIC_API_KEY` (the most common first-time-user failure) surfaces
as a 600-line traceback ending in:

    anthropic.AuthenticationError: Error code: 401 - {'type': 'error',
    'error': {'type': 'authentication_error', 'message': '...'}}

Users hate that. The fix is small: catch the SDK's typed exceptions
at the CLI command boundary and re-raise as `typer.Exit` with a
one-sentence explanation + remediation pointer.

Used as a context manager around agent invocations:

    from efterlev.cli.friendly_errors import friendly_llm_error_handler

    with friendly_llm_error_handler():
        report = agent.run(input)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import typer


def format_llm_error(exc: Exception) -> tuple[str, str | None]:
    """Map an LLM/credential exception to (one_line_message, hint).

    Returns a `(message, hint)` pair. The message is what the user
    sees first (one sentence, no SDK-shape jargon). The hint is the
    actionable next step (env var to set, command to run, doc to
    read). `hint` may be None for errors that don't have a single
    obvious remediation.

    Lazily imports `anthropic` since it's an optional runtime dep.
    """
    # Lazy SDK import — anthropic is optional at runtime.
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return ("anthropic SDK not installed", "Install efterlev with the [agents] extra.")

    if isinstance(exc, anthropic.AuthenticationError):
        return (
            "ANTHROPIC_API_KEY is missing or invalid (HTTP 401 from Anthropic).",
            (
                "Set ANTHROPIC_API_KEY to a real key from "
                "https://console.anthropic.com, or switch to the Bedrock "
                "backend in .efterlev/config.toml. Run `efterlev doctor` "
                "to inspect."
            ),
        )
    if isinstance(exc, anthropic.PermissionDeniedError):
        return (
            "Anthropic API permission denied (HTTP 403).",
            (
                "Verify the API key has access to the requested model. "
                "Some keys are scoped to specific models or regions; "
                "check https://console.anthropic.com under your key's settings."
            ),
        )
    if isinstance(exc, anthropic.RateLimitError):
        return (
            "Rate-limited by Anthropic after exhausting retries (HTTP 429).",
            (
                "Wait a minute and retry. If this happens repeatedly, "
                "reduce concurrency or contact Anthropic to raise your "
                "tier limit."
            ),
        )
    if isinstance(exc, anthropic.NotFoundError):
        return (
            "Model not found at Anthropic (HTTP 404).",
            (
                "The model id in .efterlev/config.toml may be misspelled or "
                "deprecated. Check the available models in your Anthropic "
                "console; v0 defaults are claude-opus-4-7 and "
                "claude-sonnet-4-6."
            ),
        )
    if isinstance(exc, anthropic.BadRequestError):
        return (
            "Anthropic rejected the request as malformed (HTTP 400).",
            (
                "This is usually a code-level bug (prompt too long, "
                "schema mismatch). Capture the request and file an issue."
            ),
        )
    if isinstance(exc, anthropic.APITimeoutError):
        return (
            "Anthropic API timed out after retries.",
            (
                "Anthropic was slow or unreachable. Try again; if "
                "persistent, check https://status.anthropic.com."
            ),
        )
    if isinstance(exc, anthropic.APIConnectionError):
        return (
            "Could not reach api.anthropic.com.",
            (
                "Check your network. Behind a proxy? Set HTTPS_PROXY. "
                "On GovCloud? Switch to the Bedrock backend instead."
            ),
        )
    if isinstance(exc, anthropic.InternalServerError):
        return (
            "Anthropic returned an internal server error (HTTP 5xx) after retries.",
            (
                "Transient on Anthropic's side. Retry in a minute; "
                "check https://status.anthropic.com if persistent."
            ),
        )
    # Fallback for any other anthropic.APIError (catch-all SDK base).
    if isinstance(exc, anthropic.APIError):
        return (
            f"Anthropic API error: {type(exc).__name__}",
            "Re-run `efterlev doctor` and verify your config.",
        )
    # Unknown exception — let the original message through.
    return (str(exc), None)


@contextmanager
def friendly_llm_error_handler() -> Iterator[None]:
    """Catch SDK errors at the CLI boundary and exit with friendly text.

    Usage:
        with friendly_llm_error_handler():
            report = agent.run(input)

    On a recognized SDK exception:
      - typer.echo's a one-sentence "error: <message>" line on stderr.
      - typer.echo's a "  hint: <hint>" line on stderr if there's a
        remediation.
      - Raises typer.Exit(code=1) — the CLI exits non-zero with no
        traceback. The original exception is chained for `--help`/
        debug log inspection but doesn't print to the user.

    Exceptions that aren't anthropic errors propagate unchanged so the
    Python traceback still surfaces real bugs.
    """
    try:
        yield
    except Exception as e:
        try:
            import anthropic
        except ImportError:  # pragma: no cover
            raise

        if not isinstance(e, anthropic.APIError):
            raise

        message, hint = format_llm_error(e)
        typer.echo(f"error: {message}", err=True)
        if hint:
            typer.echo(f"  hint: {hint}", err=True)
        raise typer.Exit(code=1) from e
