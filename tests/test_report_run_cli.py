"""CLI tests for `efterlev report run` (Priority 3.3).

The one-command pipeline chains init → scan → agent gap → agent
document → poam. We test the orchestration layer's correctness:

  - Stages run in the right order.
  - --skip-* flags actually skip the right stages.
  - .efterlev/ pre-existence skips init by default.
  - Non-zero exit from any stage stops the pipeline.

We don't re-test what each stage does — those are tested in their own
test files. Here we mock-shim the pipeline by replacing the actual
agent calls with fake ones so the test is fast and offline.
"""

from __future__ import annotations

from pathlib import Path

import typer
from typer.testing import CliRunner

from efterlev.cli.main import app, report_app

runner = CliRunner()


def _stub_command_outcomes(monkeypatch: object, calls: list[tuple[str, list[str]]]) -> None:
    """Replace `app(args, standalone_mode=False)` with a fake that records
    the calls and returns 0. The stub is set on the report_app module
    where the pipeline orchestrator imports `app` from."""
    from efterlev.cli import main as cli_main

    original = cli_main.app

    def fake_app(args: list[str], standalone_mode: bool = False) -> int:
        # Record (stage_name_inferred, args). The stage name is the
        # subcommand in the args list, joined for multi-word commands.
        stage = f"agent {args[1]}" if args[0] == "agent" else args[0]
        calls.append((stage, list(args)))
        return 0

    monkeypatch.setattr(cli_main, "app", fake_app, raising=True)
    # Also need to swap on the `app` symbol the report_run function uses.
    # `report_run` imports `app` as a global; monkeypatching cli_main.app
    # is sufficient because Python attribute lookup goes through the
    # module's namespace at call time.
    yield original


# --- pipeline orchestration -----------------------------------------------


def test_pipeline_runs_init_scan_gap_document_poam_in_order(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    """A fresh target with no .efterlev/ runs all five stages in the
    documented order."""
    calls: list[tuple[str, list[str]]] = []
    list(_stub_command_outcomes(monkeypatch, calls))  # consume the generator

    result = runner.invoke(app, ["report", "run", "--target", str(tmp_path)])
    assert result.exit_code == 0, result.output
    stages = [name for name, _ in calls]
    assert stages == ["init", "scan", "agent gap", "agent document", "poam"]


def test_pipeline_skips_init_when_frmr_cache_exists(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    """An already-initialized workspace (FRMR cache present) skips the
    init step automatically so re-running the pipeline doesn't fail with
    "directory exists"."""
    cache = tmp_path / ".efterlev" / "cache" / "frmr_document.json"
    cache.parent.mkdir(parents=True)
    cache.write_text('{"info": {"version": "stub"}}', encoding="utf-8")
    calls: list[tuple[str, list[str]]] = []
    list(_stub_command_outcomes(monkeypatch, calls))

    result = runner.invoke(app, ["report", "run", "--target", str(tmp_path)])
    assert result.exit_code == 0, result.output
    stages = [name for name, _ in calls]
    assert "init" not in stages
    assert stages == ["scan", "agent gap", "agent document", "poam"]


def test_pipeline_uses_force_init_on_half_initialized_workspace(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    """When `.efterlev/manifests/` is committed but the FRMR cache is
    gitignored (the canonical pattern for repos with Evidence Manifests),
    a fresh clone has the workspace dir present but the cache missing.

    Without this fix, init would be skipped (dir exists → assumed
    initialized) and `scan` would crash with "FRMR cache missing." With
    the fix, init runs but with `--force` so it regenerates the cache
    while preserving the manifests under `.efterlev/manifests/`.

    Regression test for govnotes-demo CI failure 2026-04-30.
    """
    # Half-initialized workspace: manifests committed, cache missing.
    manifests = tmp_path / ".efterlev" / "manifests"
    manifests.mkdir(parents=True)
    (manifests / "afr-fsi.yml").write_text("ksi: KSI-AFR-FSI\n", encoding="utf-8")
    calls: list[tuple[str, list[str]]] = []
    list(_stub_command_outcomes(monkeypatch, calls))

    result = runner.invoke(app, ["report", "run", "--target", str(tmp_path)])
    assert result.exit_code == 0, result.output
    stages = [name for name, _ in calls]
    # Init must run (cache is missing), AND it must use --force (the dir
    # already exists from the committed manifests).
    assert stages[0] == "init"
    init_args = calls[0][1]
    assert "--force" in init_args, f"expected --force in init args, got {init_args}"


def test_skip_init_flag_skips_init_even_on_fresh_workspace(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    """Explicit --skip-init takes precedence (e.g., when an external
    process has already initialized but in a non-standard layout)."""
    calls: list[tuple[str, list[str]]] = []
    list(_stub_command_outcomes(monkeypatch, calls))

    result = runner.invoke(app, ["report", "run", "--target", str(tmp_path), "--skip-init"])
    assert result.exit_code == 0, result.output
    stages = [name for name, _ in calls]
    assert "init" not in stages


def test_skip_document_flag_skips_documentation_stage(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    """--skip-document drops the Documentation Agent stage. Useful for
    iteration loops focused on Gap classification."""
    calls: list[tuple[str, list[str]]] = []
    list(_stub_command_outcomes(monkeypatch, calls))

    result = runner.invoke(app, ["report", "run", "--target", str(tmp_path), "--skip-document"])
    assert result.exit_code == 0, result.output
    stages = [name for name, _ in calls]
    assert "agent document" not in stages
    # Other stages still run.
    assert "agent gap" in stages


def test_skip_poam_flag_skips_poam_stage(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[tuple[str, list[str]]] = []
    list(_stub_command_outcomes(monkeypatch, calls))

    result = runner.invoke(app, ["report", "run", "--target", str(tmp_path), "--skip-poam"])
    assert result.exit_code == 0, result.output
    stages = [name for name, _ in calls]
    assert "poam" not in stages
    assert "agent document" in stages


def test_skip_all_optional_stages(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    """--skip-init --skip-document --skip-poam runs only scan + gap."""
    calls: list[tuple[str, list[str]]] = []
    list(_stub_command_outcomes(monkeypatch, calls))

    result = runner.invoke(
        app,
        [
            "report",
            "run",
            "--target",
            str(tmp_path),
            "--skip-init",
            "--skip-document",
            "--skip-poam",
        ],
    )
    assert result.exit_code == 0, result.output
    stages = [name for name, _ in calls]
    assert stages == ["scan", "agent gap"]


# --- failure propagation --------------------------------------------------


def test_pipeline_stops_on_raised_typer_exit(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    """If a stage raises typer.Exit with non-zero code, the pipeline
    stops and the orchestrator propagates that code (exception path)."""
    from efterlev.cli import main as cli_main

    calls: list[tuple[str, list[str]]] = []

    def failing_app(args: list[str], standalone_mode: bool = False) -> None:
        stage = f"agent {args[1]}" if args[0] == "agent" else args[0]
        calls.append((stage, list(args)))
        if stage == "agent gap":
            raise typer.Exit(code=3)

    monkeypatch.setattr(cli_main, "app", failing_app, raising=True)

    result = runner.invoke(app, ["report", "run", "--target", str(tmp_path), "--skip-init"])
    assert result.exit_code == 3
    # Stages after `agent gap` did NOT run.
    stages = [name for name, _ in calls]
    assert "agent gap" in stages
    assert "agent document" not in stages
    assert "poam" not in stages


def test_pipeline_stops_on_returned_non_zero_exit_code(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    """Click with `standalone_mode=False` RETURNS the exit code as an int
    rather than raising — that's the real production code path. The
    orchestrator must catch that case too. (This test guards the bug
    that PR #66 missed: failed stages slipping through because the
    orchestrator only caught the exception path.)"""
    from efterlev.cli import main as cli_main

    calls: list[tuple[str, list[str]]] = []

    def returning_app(args: list[str], standalone_mode: bool = False) -> int | None:
        stage = f"agent {args[1]}" if args[0] == "agent" else args[0]
        calls.append((stage, list(args)))
        if stage == "agent gap":
            return 3
        return None

    monkeypatch.setattr(cli_main, "app", returning_app, raising=True)

    result = runner.invoke(app, ["report", "run", "--target", str(tmp_path), "--skip-init"])
    assert result.exit_code == 3
    # Stages after `agent gap` did NOT run.
    stages = [name for name, _ in calls]
    assert "agent gap" in stages
    assert "agent document" not in stages
    assert "poam" not in stages
    # And — crucially — the orchestrator did NOT print "Pipeline complete."
    assert "Pipeline complete" not in result.output


# --- subcommand registration ----------------------------------------------


def test_report_run_in_help() -> None:
    result = runner.invoke(app, ["report", "--help"])
    assert result.exit_code == 0
    assert "run" in result.output


def test_report_run_help_documents_skip_flags() -> None:
    # Click/typer wrap help output to terminal width, which on CI runners
    # can split long flag names across line boundaries with whitespace
    # padding. Normalize whitespace + strip ANSI codes before asserting.
    import re

    result = runner.invoke(app, ["report", "run", "--help"])
    assert result.exit_code == 0
    # Strip ANSI escape codes and collapse whitespace to single spaces.
    normalized = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    normalized = re.sub(r"\s+", " ", normalized)
    assert "--skip-init" in normalized
    assert "--skip-document" in normalized
    assert "--skip-poam" in normalized


# --- output formatting ----------------------------------------------------


def test_pipeline_prints_stage_headers(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    """The orchestrator prints `━━━ [N/M] stage ━━━` headers between
    stages so reviewers can scan stdout for stage boundaries."""
    calls: list[tuple[str, list[str]]] = []
    list(_stub_command_outcomes(monkeypatch, calls))

    result = runner.invoke(app, ["report", "run", "--target", str(tmp_path), "--skip-init"])
    assert result.exit_code == 0
    # Stage headers visible.
    assert "[1/4] scan" in result.output
    assert "[2/4] agent gap" in result.output
    # Pipeline-complete marker on success.
    assert "Pipeline complete" in result.output


def test_pipeline_announces_stages_at_start(  # type: ignore[no-untyped-def]
    tmp_path: Path, monkeypatch
) -> None:
    """First line shows the planned pipeline (so the user sees the
    sequence before stages start running)."""
    calls: list[tuple[str, list[str]]] = []
    list(_stub_command_outcomes(monkeypatch, calls))

    result = runner.invoke(app, ["report", "run", "--target", str(tmp_path), "--skip-init"])
    assert "scan → agent gap → agent document → poam" in result.output


# Ensure subapp object reference is stable across imports (defensive).
def test_report_app_object_is_used_in_main_app() -> None:
    assert report_app is not None
