"""Tests for `efterlev doctor` (Priority 3).

The doctor checks are pure functions over environment + filesystem
state, easy to unit-test by manipulating env vars and tmp_path.
The CLI command tests live below alongside.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from efterlev.cli.doctor import (
    Check,
    check_anthropic_api_key,
    check_bedrock_credentials,
    check_efterlev_dir,
    check_frmr_cache,
    check_python_version,
    has_failures,
    run_doctor_checks,
)
from efterlev.cli.main import app

runner = CliRunner()


# --- check_python_version --------------------------------------------------


def test_python_version_passes_on_supported_python() -> None:
    """Tests run on Python ≥3.10 by definition (pyproject.toml gates this)."""
    c = check_python_version()
    assert c.status == "pass"
    assert "Python" in c.detail


# --- check_anthropic_api_key ----------------------------------------------


def test_anthropic_api_key_warns_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    c = check_anthropic_api_key()
    assert c.status == "warn"
    assert "is not set" in c.detail
    assert c.hint is not None
    assert "console.anthropic.com" in c.hint


def test_anthropic_api_key_warns_on_wrong_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "wrong_prefix_xxxxx")
    c = check_anthropic_api_key()
    assert c.status == "warn"
    assert "doesn't start with 'sk-ant-'" in c.detail


def test_anthropic_api_key_passes_on_realistic_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-" + "x" * 100)
    c = check_anthropic_api_key()
    assert c.status == "pass"
    assert "sk-ant-" in c.detail


# --- check_efterlev_dir ---------------------------------------------------


def test_efterlev_dir_passes_when_dir_exists(tmp_path: Path) -> None:
    (tmp_path / ".efterlev").mkdir()
    c = check_efterlev_dir(tmp_path)
    assert c.status == "pass"


def test_efterlev_dir_warns_when_missing(tmp_path: Path) -> None:
    c = check_efterlev_dir(tmp_path)
    assert c.status == "warn"
    assert "not initialized" in c.detail
    assert c.hint is not None
    assert "efterlev init" in c.hint


# --- check_frmr_cache -----------------------------------------------------


def test_frmr_cache_passes_when_recent(tmp_path: Path) -> None:
    cache = tmp_path / ".efterlev" / "cache" / "frmr_document.json"
    cache.parent.mkdir(parents=True)
    cache.write_text("{}", encoding="utf-8")
    c = check_frmr_cache(tmp_path)
    assert c.status == "pass"


def test_frmr_cache_warns_when_missing(tmp_path: Path) -> None:
    c = check_frmr_cache(tmp_path)
    assert c.status == "warn"
    assert "missing" in c.detail
    assert c.hint is not None
    assert "efterlev init" in c.hint


def test_frmr_cache_warns_when_stale(tmp_path: Path) -> None:
    cache = tmp_path / ".efterlev" / "cache" / "frmr_document.json"
    cache.parent.mkdir(parents=True)
    cache.write_text("{}", encoding="utf-8")
    # Force mtime to 100 days ago.
    old = time.time() - 100 * 86400
    cache.touch()
    import os

    os.utime(cache, (old, old))
    c = check_frmr_cache(tmp_path)
    assert c.status == "warn"
    assert "days old" in c.detail


# --- check_bedrock_credentials --------------------------------------------


def _patch_boto_session_creds(monkeypatch: pytest.MonkeyPatch, creds_obj: object | None) -> None:
    """Force `boto3.Session().get_credentials()` to return a stub.

    The doctor uses boto3's full credential chain (env, shared file,
    profile, IMDS, SSO) instead of just env vars. Tests can't rely on
    env-var-only stubbing anymore — they need to control what the
    chain reports.
    """
    import boto3

    class _FakeSession:
        def get_credentials(self) -> object | None:
            return creds_obj

    monkeypatch.setattr(boto3, "Session", lambda *a, **kw: _FakeSession())


def test_bedrock_credentials_warn_when_no_creds_resolvable(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env vars and no shared-credential file → boto3 returns None."""
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE", "AWS_REGION"):
        monkeypatch.delenv(var, raising=False)
    _patch_boto_session_creds(monkeypatch, None)
    c = check_bedrock_credentials()
    assert c.status == "warn"
    assert "No AWS credentials resolvable" in c.detail


def test_bedrock_credentials_warn_when_no_region(monkeypatch: pytest.MonkeyPatch) -> None:
    """Creds resolve from ANY source, but region is unset."""
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    _patch_boto_session_creds(monkeypatch, object())  # truthy stand-in for a Credentials object
    c = check_bedrock_credentials()
    assert c.status == "warn"
    assert "no region configured" in c.detail


def test_bedrock_credentials_pass_when_creds_resolve_via_shared_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real-world fix: `~/.aws/credentials` + `aws configure set region` are
    the canonical install pattern. Earlier env-var-only logic false-warned
    on this path even though boto3's runtime client used those creds fine.
    """
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_REGION", "us-gov-west-1")
    _patch_boto_session_creds(monkeypatch, object())  # creds came from ~/.aws/credentials
    c = check_bedrock_credentials()
    assert c.status == "pass"
    assert "Bedrock backend usable" in c.detail


def test_bedrock_credentials_pass_with_profile_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "govcloud")
    monkeypatch.setenv("AWS_REGION", "us-gov-west-1")
    _patch_boto_session_creds(monkeypatch, object())
    c = check_bedrock_credentials()
    assert c.status == "pass"


def test_anthropic_api_key_skipped_when_backend_is_bedrock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workspaces configured for Bedrock shouldn't generate noise about a
    missing Anthropic key — that path doesn't use one.
    """
    from efterlev.cli.doctor import check_anthropic_api_key

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    c = check_anthropic_api_key(configured_backend="bedrock")
    assert c.status == "pass"
    assert "skipped" in c.detail.lower()


# --- run_doctor_checks aggregator -----------------------------------------


def test_run_doctor_checks_returns_all_categories(tmp_path: Path) -> None:
    """All 5 checks run in a defined order."""
    (tmp_path / ".efterlev").mkdir()
    checks = run_doctor_checks(tmp_path)
    names = [c.name for c in checks]
    assert names == [
        "python_version",
        "efterlev_dir",
        "frmr_cache",
        "anthropic_api_key",
        "bedrock_credentials",
    ]


def test_has_failures_only_counts_fail_status() -> None:
    """`warn` does NOT count as failure — exit-code gate is only `fail`."""
    only_warns = [
        Check(name="x", status="warn", detail="."),
        Check(name="y", status="warn", detail="."),
    ]
    assert has_failures(only_warns) is False

    has_fail = [
        Check(name="x", status="warn", detail="."),
        Check(name="y", status="fail", detail="."),
    ]
    assert has_failures(has_fail) is True


# --- CLI integration ------------------------------------------------------


def test_doctor_cli_prints_per_check_lines(tmp_path: Path) -> None:
    (tmp_path / ".efterlev").mkdir()
    result = runner.invoke(app, ["doctor", "--target", str(tmp_path)])
    # Doctor exits 0 when no `fail` status — only the API-key warn etc.
    assert result.exit_code == 0
    out = result.output
    assert "Efterlev doctor — pre-flight checks" in out
    assert "python_version" in out
    assert "anthropic_api_key" in out
    assert "frmr_cache" in out
    assert "bedrock_credentials" in out
    assert "summary:" in out
    assert "pass" in out


def test_doctor_subcommand_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.output


def test_doctor_warning_lines_print_hint(tmp_path: Path) -> None:
    """Warn-status checks render their `hint` text inline."""
    # Empty target → no .efterlev dir → warn with hint.
    result = runner.invoke(app, ["doctor", "--target", str(tmp_path)])
    assert "hint:" in result.output
    assert "efterlev init" in result.output
