"""First-run wizard for `efterlev init`.

Priority 3.4 (2026-04-28). New users running `efterlev init` for the
first time without `ANTHROPIC_API_KEY` set will see agent commands
fail later with a credential error. The wizard catches that at init
time, shows a friendly intro, and points the user at the right
configuration before they invoke an agent and hit a wall.

Designed to be CI-safe: when stdout/stdin isn't a TTY, the wizard
auto-skips silently. CI environments that programmatically run
`efterlev init` aren't surprised by an interactive prompt.

The wizard does NOT modify config or env vars on its own — it
explains what to do and exits cleanly. The user makes the actual
change. This is a deliberate design: a wizard that silently writes
config can mask later confusion ("why is my .efterlev/config.toml
configured for Bedrock when I never asked?"). Showing-and-telling is
strictly more honest.
"""

from __future__ import annotations

import os
import sys

import typer


def is_interactive() -> bool:
    """True iff both stdin and stdout are TTYs.

    CI environments and `efterlev init < /dev/null` style invocations
    will have at least one of these as non-TTY; in those cases we
    auto-skip the wizard.
    """
    return sys.stdin.isatty() and sys.stdout.isatty()


def has_any_llm_credentials() -> bool:
    """Heuristic: is at least one LLM backend plausibly configured?

    Returns True iff:
      - ANTHROPIC_API_KEY is set in env, OR
      - AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY are both set, OR
      - AWS_PROFILE is set.

    The wizard only fires when this returns False — i.e., the user
    has no plausible credentials and is running a non-Bedrock-CLI
    init.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    if os.environ.get("AWS_PROFILE"):
        return True
    return bool(os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))


def show_first_run_intro(*, llm_backend: str) -> None:
    """Print the first-run wizard intro to stderr.

    Called from `efterlev init` BEFORE the actual init logic when
    the wizard's preconditions are met (interactive + no creds).
    Returns nothing; the user reads the message and decides.

    The intro covers:
      - Welcome + what efterlev needs to be useful (an LLM backend)
      - Two paths: Anthropic API (default) vs AWS Bedrock
      - The exact env var or CLI flag to set
      - That init still proceeds — the warning doesn't block

    Output goes to stderr so it doesn't pollute stdout for users
    piping `efterlev init`'s output (rare but possible).
    """
    typer.echo("", err=True)
    typer.echo("━━━ Efterlev — first-run setup ━━━", err=True)
    typer.echo("", err=True)
    typer.echo(
        "It looks like neither ANTHROPIC_API_KEY nor AWS credentials are set",
        err=True,
    )
    typer.echo("in your environment. The agent commands need an LLM backend:", err=True)
    typer.echo("", err=True)

    if llm_backend == "bedrock":
        typer.echo("  You're initializing with --llm-backend=bedrock.", err=True)
        typer.echo("  Set AWS credentials before running any `efterlev agent` command:", err=True)
        typer.echo("", err=True)
        typer.echo("    export AWS_ACCESS_KEY_ID=AKIA...", err=True)
        typer.echo("    export AWS_SECRET_ACCESS_KEY=...", err=True)
        typer.echo("    export AWS_REGION=us-gov-west-1   # or your region", err=True)
        typer.echo("", err=True)
        typer.echo("  Or use AWS_PROFILE if you have a configured profile.", err=True)
    else:
        typer.echo("  Easiest path — Anthropic API:", err=True)
        typer.echo("", err=True)
        typer.echo("    export ANTHROPIC_API_KEY=sk-ant-...", err=True)
        typer.echo("", err=True)
        typer.echo("  Get a key at https://console.anthropic.com.", err=True)
        typer.echo("", err=True)
        typer.echo("  FedRAMP-aware path — AWS Bedrock (re-init with):", err=True)
        typer.echo("", err=True)
        typer.echo(
            "    efterlev init --force --llm-backend bedrock --llm-region us-gov-west-1",
            err=True,
        )

    typer.echo("", err=True)
    typer.echo(
        "Init will proceed now. Run `efterlev doctor` after setting credentials",
        err=True,
    )
    typer.echo("to verify the configuration.", err=True)
    typer.echo("", err=True)


def maybe_show_first_run_intro(*, llm_backend: str) -> None:
    """Decide whether to fire the wizard, then fire if appropriate.

    Centralized so `efterlev init` calls this single helper without
    needing to repeat the precondition checks.
    """
    if not is_interactive():
        return
    if has_any_llm_credentials():
        return
    show_first_run_intro(llm_backend=llm_backend)
