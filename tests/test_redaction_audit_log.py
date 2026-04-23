"""Tests for the redaction audit-log infrastructure:

  - `write_redaction_log` creates/appends .efterlev/redacted.log with
    0600 perms and JSONL records.
  - `active_redaction_ledger` context manager + `get_active_redaction_ledger`
    thread a ledger through without modifying agent signatures.
  - `format_evidence_for_prompt` picks up the active ledger when no
    explicit kwarg is passed.
  - The `efterlev redaction review` CLI reads the log and summarizes.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from efterlev.agents.base import format_evidence_for_prompt
from efterlev.cli.main import app
from efterlev.llm.scrubber import (
    RedactionEvent,
    RedactionLedger,
    active_redaction_ledger,
    get_active_redaction_ledger,
    write_redaction_log,
)
from efterlev.models import Evidence, SourceRef

runner = CliRunner()


# --- write_redaction_log ---------------------------------------------------


def _make_ledger_with_event(
    pattern: str = "aws_access_key_id", prefix: str = "deadbeef"
) -> RedactionLedger:
    ledger = RedactionLedger()
    ledger.extend(
        [
            RedactionEvent(
                timestamp=datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC),
                pattern_name=pattern,
                sha256_prefix=prefix,
                context_hint="evidence[x]:0",
            )
        ]
    )
    return ledger


def test_write_redaction_log_creates_0600_file(tmp_path: Path) -> None:
    log = tmp_path / ".efterlev" / "redacted.log"
    ledger = _make_ledger_with_event()

    count = write_redaction_log(ledger, log, scan_id="scan-A")

    assert count == 1
    assert log.is_file()
    mode = stat.S_IMODE(os.stat(log).st_mode)
    # User rw only — group/other must have no permissions.
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"


def test_write_redaction_log_empty_ledger_is_noop(tmp_path: Path) -> None:
    log = tmp_path / ".efterlev" / "redacted.log"
    empty = RedactionLedger()

    count = write_redaction_log(empty, log, scan_id="scan-A")

    assert count == 0
    assert not log.exists(), "empty ledger should not create the log file"


def test_write_redaction_log_appends_existing(tmp_path: Path) -> None:
    log = tmp_path / ".efterlev" / "redacted.log"

    write_redaction_log(_make_ledger_with_event("aws_access_key_id"), log, scan_id="s1")
    write_redaction_log(_make_ledger_with_event("github_token"), log, scan_id="s2")

    lines = [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 2
    assert lines[0]["scan_id"] == "s1"
    assert lines[1]["scan_id"] == "s2"
    assert lines[1]["pattern_name"] == "github_token"


def test_write_redaction_log_reaffirms_0600_on_append(tmp_path: Path) -> None:
    # Create the log with loose perms, then append → perms should clamp to 0600.
    log = tmp_path / ".efterlev" / "redacted.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text('{"scan_id": "prior"}\n', encoding="utf-8")
    os.chmod(log, 0o644)  # deliberately lax

    write_redaction_log(_make_ledger_with_event(), log, scan_id="after")

    assert stat.S_IMODE(os.stat(log).st_mode) == 0o600


def test_audit_log_never_contains_secret_value(tmp_path: Path) -> None:
    # Ledger events carry only the sha256_prefix, not the original value —
    # regression test that the serializer doesn't expose the secret.
    log = tmp_path / ".efterlev" / "redacted.log"
    ledger = _make_ledger_with_event(prefix="a1b2c3d4")

    write_redaction_log(ledger, log, scan_id="audit-safe")

    contents = log.read_text(encoding="utf-8")
    assert "a1b2c3d4" in contents  # prefix present (for cross-reference)
    # Ensure no secret-ish token format leaks through (defensive).
    assert "AKIA" not in contents
    assert "ghp_" not in contents
    assert "sk_live_" not in contents


# --- active_redaction_ledger context manager -------------------------------


def test_active_redaction_ledger_sets_and_resets_contextvar() -> None:
    assert get_active_redaction_ledger() is None
    ledger = RedactionLedger()
    with active_redaction_ledger(ledger):
        assert get_active_redaction_ledger() is ledger
    assert get_active_redaction_ledger() is None


def test_format_evidence_uses_active_ledger_when_no_kwarg() -> None:
    """The motivating use case: CLI activates a ledger; agents call
    `format_evidence_for_prompt` without threading it explicitly;
    redactions still get captured."""
    ev = Evidence.create(
        detector_id="aws.iam_user_access_keys",
        source_ref=SourceRef(file="iam.tf", line_start=1, line_end=5),
        ksis_evidenced=[],
        controls_evidenced=["IA-2"],
        content={"leaked": "AKIAIOSFODNN7EXAMPLE"},
        timestamp=datetime.now(UTC),
    )
    ledger = RedactionLedger()
    with active_redaction_ledger(ledger):
        prompt = format_evidence_for_prompt([ev], nonce="test1234")

    assert "AKIAIOSFODNN7EXAMPLE" not in prompt
    assert ledger.count == 1, "active ledger should have captured the redaction"


def test_explicit_redaction_ledger_kwarg_wins_over_active() -> None:
    ev = Evidence.create(
        detector_id="aws.iam_user_access_keys",
        source_ref=SourceRef(file="iam.tf", line_start=1, line_end=5),
        ksis_evidenced=[],
        controls_evidenced=["IA-2"],
        content={"leaked": "AKIAIOSFODNN7EXAMPLE"},
        timestamp=datetime.now(UTC),
    )
    active = RedactionLedger()
    explicit = RedactionLedger()
    with active_redaction_ledger(active):
        format_evidence_for_prompt([ev], nonce="test1234", redaction_ledger=explicit)

    assert explicit.count == 1, "explicit ledger should record the event"
    assert active.count == 0, "active ledger should NOT record when kwarg wins"


# --- CLI: efterlev redaction review ----------------------------------------


def _seed_log(tmp_path: Path, records: list[dict]) -> Path:
    """Create a `.efterlev/redacted.log` with the given records."""
    log = tmp_path / ".efterlev" / "redacted.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
        encoding="utf-8",
    )
    os.chmod(log, 0o600)
    return log


def test_redaction_review_reports_no_log(tmp_path: Path) -> None:
    # No .efterlev/redacted.log exists; review should exit 0 with a
    # "no log" message rather than crashing.
    result = runner.invoke(app, ["redaction", "review", "--target", str(tmp_path)])
    assert result.exit_code == 0
    assert "No redaction log" in result.output


def test_redaction_review_summary_groups_by_scan(tmp_path: Path) -> None:
    _seed_log(
        tmp_path,
        [
            {
                "scan_id": "s1",
                "timestamp": "2026-04-23T12:00:00+00:00",
                "pattern_name": "aws_access_key_id",
                "sha256_prefix": "aabbccdd",
                "context_hint": "evidence[X]:0",
            },
            {
                "scan_id": "s1",
                "timestamp": "2026-04-23T12:00:01+00:00",
                "pattern_name": "github_token",
                "sha256_prefix": "11223344",
                "context_hint": "evidence[X]:1",
            },
            {
                "scan_id": "s2",
                "timestamp": "2026-04-23T13:00:00+00:00",
                "pattern_name": "aws_access_key_id",
                "sha256_prefix": "ddccbbaa",
                "context_hint": "source_file[main.tf]",
            },
        ],
    )
    result = runner.invoke(app, ["redaction", "review", "--target", str(tmp_path)])
    assert result.exit_code == 0
    # Summary lists both scans with their counts.
    assert "s1" in result.output
    assert "s2" in result.output
    # Summary carries the pattern-count shape like "2xaws_access_key_id".
    assert "aws_access_key_id" in result.output
    assert "github_token" in result.output


def test_redaction_review_scan_id_shows_per_event_detail(tmp_path: Path) -> None:
    _seed_log(
        tmp_path,
        [
            {
                "scan_id": "deepscan",
                "timestamp": "2026-04-23T12:00:00+00:00",
                "pattern_name": "aws_access_key_id",
                "sha256_prefix": "aabbccdd",
                "context_hint": "evidence[aws.iam_user_access_keys]:0",
            },
        ],
    )
    result = runner.invoke(
        app, ["redaction", "review", "--target", str(tmp_path), "--scan-id", "deepscan"]
    )
    assert result.exit_code == 0
    assert "aws_access_key_id" in result.output
    assert "sha256:aabbccdd" in result.output
    assert "evidence[aws.iam_user_access_keys]:0" in result.output


def test_redaction_review_unknown_scan_id_exits_1(tmp_path: Path) -> None:
    _seed_log(
        tmp_path,
        [
            {
                "scan_id": "real-scan",
                "timestamp": "2026-04-23T12:00:00+00:00",
                "pattern_name": "aws_access_key_id",
                "sha256_prefix": "aabbccdd",
                "context_hint": "evidence[X]:0",
            },
        ],
    )
    result = runner.invoke(
        app,
        ["redaction", "review", "--target", str(tmp_path), "--scan-id", "nonexistent"],
    )
    assert result.exit_code == 1
    assert "No redactions recorded" in result.output


def test_redaction_review_tolerates_malformed_lines(tmp_path: Path) -> None:
    # A malformed line shouldn't crash the reader — just get skipped.
    log = tmp_path / ".efterlev" / "redacted.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        '{"scan_id": "good", "timestamp": "t", "pattern_name": "aws_access_key_id", '
        '"sha256_prefix": "ab", "context_hint": "c"}\n'
        "this line is not valid json\n"
        '{"scan_id": "good-too", "timestamp": "t", "pattern_name": "github_token", '
        '"sha256_prefix": "cd", "context_hint": "c"}\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["redaction", "review", "--target", str(tmp_path)])
    assert result.exit_code == 0
    assert "good" in result.output
    assert "good-too" in result.output


def test_redaction_review_limit_respected(tmp_path: Path) -> None:
    records = [
        {
            "scan_id": f"s{i}",
            "timestamp": f"2026-04-23T12:{i:02}:00+00:00",
            "pattern_name": "aws_access_key_id",
            "sha256_prefix": f"{i:08x}",
            "context_hint": f"evidence[X]:{i}",
        }
        for i in range(10)
    ]
    _seed_log(tmp_path, records)

    result = runner.invoke(
        app, ["redaction", "review", "--target", str(tmp_path), "--limit", "3"]
    )
    assert result.exit_code == 0
    # Most-recent 3 shown: s7, s8, s9. Earlier not shown → explicitly named.
    assert "s9" in result.output
    assert "7 earlier scan(s) not shown" in result.output


# --- regression guard: no existing agent test broke ------------------------


def test_active_ledger_unset_after_context_exit_even_on_exception() -> None:
    ledger = RedactionLedger()

    class _BoomError(Exception):
        pass

    with pytest.raises(_BoomError), active_redaction_ledger(ledger):
        raise _BoomError()

    assert get_active_redaction_ledger() is None
