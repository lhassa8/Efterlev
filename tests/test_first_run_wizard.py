"""Tests for the first-run wizard at `efterlev init`.

Priority 3.4 (2026-04-28). The wizard fires only when both stdin and
stdout are TTYs AND no LLM credentials are configured. Tests cover
the precondition logic, the intro-text content (Anthropic vs Bedrock
paths), and that the wizard does NOT block init when fired (it's
informational only).
"""

from __future__ import annotations

import pytest

from efterlev.cli.first_run_wizard import (
    has_any_llm_credentials,
    is_interactive,
    maybe_show_first_run_intro,
    show_first_run_intro,
)

# --- has_any_llm_credentials ----------------------------------------------


def test_no_credentials_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_PROFILE",
    ):
        monkeypatch.delenv(var, raising=False)
    assert has_any_llm_credentials() is False


def test_anthropic_api_key_alone_is_enough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-...")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    assert has_any_llm_credentials() is True


def test_aws_profile_alone_is_enough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "govcloud")
    assert has_any_llm_credentials() is True


def test_aws_access_keys_pair_is_enough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA...")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    assert has_any_llm_credentials() is True


def test_only_one_aws_key_is_not_enough(monkeypatch: pytest.MonkeyPatch) -> None:
    """AWS_ACCESS_KEY_ID without AWS_SECRET_ACCESS_KEY is incomplete."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA...")
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert has_any_llm_credentials() is False


# --- show_first_run_intro content -----------------------------------------


def test_anthropic_intro_mentions_console_link_and_env_var(
    capsys: pytest.CaptureFixture[str],
) -> None:
    show_first_run_intro(llm_backend="anthropic")
    out = capsys.readouterr().err
    assert "first-run setup" in out
    assert "ANTHROPIC_API_KEY" in out
    assert "console.anthropic.com" in out
    # Bedrock path is mentioned as the FedRAMP option.
    assert "Bedrock" in out or "bedrock" in out


def test_bedrock_intro_mentions_aws_credentials_and_region(
    capsys: pytest.CaptureFixture[str],
) -> None:
    show_first_run_intro(llm_backend="bedrock")
    out = capsys.readouterr().err
    assert "AWS_ACCESS_KEY_ID" in out
    assert "AWS_SECRET_ACCESS_KEY" in out
    assert "AWS_REGION" in out
    # The Anthropic-specific hint is NOT printed in the Bedrock branch.
    assert "console.anthropic.com" not in out


def test_intro_writes_to_stderr_not_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """All output goes to stderr so users piping init to a file don't
    see the wizard mixed with init's stdout."""
    show_first_run_intro(llm_backend="anthropic")
    out = capsys.readouterr()
    assert out.out == ""
    assert "first-run setup" in out.err


def test_intro_advises_running_doctor(capsys: pytest.CaptureFixture[str]) -> None:
    """The intro tells users to run `efterlev doctor` to verify their
    config — closes the loop with the doctor command from PR #64."""
    show_first_run_intro(llm_backend="anthropic")
    out = capsys.readouterr().err
    assert "efterlev doctor" in out


# --- maybe_show_first_run_intro precondition gating -----------------------


def test_skips_when_not_interactive(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-TTY (CI, piped) → wizard auto-skips silently."""
    monkeypatch.setattr("efterlev.cli.first_run_wizard.is_interactive", lambda: False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    maybe_show_first_run_intro(llm_backend="anthropic")
    out = capsys.readouterr()
    assert out.err == ""
    assert out.out == ""


def test_skips_when_credentials_already_set(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Credentials present → no wizard, even on TTY."""
    monkeypatch.setattr("efterlev.cli.first_run_wizard.is_interactive", lambda: True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-...")
    maybe_show_first_run_intro(llm_backend="anthropic")
    assert capsys.readouterr().err == ""


def test_fires_when_interactive_and_no_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The two preconditions met → intro prints."""
    monkeypatch.setattr("efterlev.cli.first_run_wizard.is_interactive", lambda: True)
    for var in (
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_PROFILE",
    ):
        monkeypatch.delenv(var, raising=False)
    maybe_show_first_run_intro(llm_backend="anthropic")
    err = capsys.readouterr().err
    assert "first-run setup" in err


# --- is_interactive (defensive smoke test) --------------------------------


def test_is_interactive_returns_bool() -> None:
    """`is_interactive` reads sys.stdin/stdout.isatty(); just verify the
    return type. The actual TTY state is environment-dependent."""
    result = is_interactive()
    assert isinstance(result, bool)
