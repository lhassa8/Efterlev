"""CLI tests for `efterlev report diff` (Priority 2.10b).

The command reads two gap-report JSON sidecars from disk, computes
the diff, and writes both `gap-diff-<ts>.html` and `gap-diff-<ts>.json`
to `.efterlev/reports/` of the target workspace. Exits with code 2 if
any KSI regressed (useful for CI gating).
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from efterlev.cli.main import app

runner = CliRunner()


def _write_sidecar(path: Path, classifications: list[tuple[str, str]]) -> None:
    """Write a minimal gap-report JSON sidecar to `path`."""
    data = {
        "schema_version": "1.0",
        "report_type": "gap",
        "generated_at": "2026-04-28T12:00:00+00:00",
        "baseline_id": "fedramp-20x-moderate",
        "frmr_version": "0.9.43-beta",
        "workspace_boundary_state": "boundary_undeclared",
        "ksi_classifications": [
            {
                "ksi_id": ksi,
                "status": status,
                "rationale": "...",
                "evidence_ids": [],
                "boundary_state": "boundary_undeclared",
            }
            for ksi, status in classifications
        ],
        "unmapped_findings": [],
        "claim_record_ids": [],
        "coverage_matrix": None,
    }
    path.write_text(json.dumps(data), encoding="utf-8")


# --- happy path -----------------------------------------------------------


def test_report_diff_writes_html_and_json_sidecar(tmp_path: Path) -> None:
    prior = tmp_path / "prior.json"
    current = tmp_path / "current.json"
    _write_sidecar(prior, [("KSI-SVC-SNT", "implemented")])
    _write_sidecar(current, [("KSI-SVC-SNT", "implemented"), ("KSI-IAM-MFA", "partial")])

    result = runner.invoke(
        app, ["report", "diff", str(prior), str(current), "--target", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "added:      1" in result.output
    assert "regressed:  0" in result.output
    assert "HTML report:" in result.output
    assert "JSON sidecar:" in result.output

    reports_dir = tmp_path / ".efterlev" / "reports"
    html_files = list(reports_dir.glob("gap-diff-*.html"))
    json_files = list(reports_dir.glob("gap-diff-*.json"))
    assert len(html_files) == 1
    assert len(json_files) == 1


def test_report_diff_exit_code_2_on_regression(tmp_path: Path) -> None:
    """A diff containing any regressed KSI exits with code 2 (useful for
    blocking CI on posture regressions)."""
    prior = tmp_path / "prior.json"
    current = tmp_path / "current.json"
    _write_sidecar(prior, [("KSI-SVC-SNT", "implemented")])
    _write_sidecar(current, [("KSI-SVC-SNT", "not_implemented")])

    result = runner.invoke(
        app, ["report", "diff", str(prior), str(current), "--target", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "regressed:  1" in result.output


def test_report_diff_exit_code_0_when_only_improvements(tmp_path: Path) -> None:
    prior = tmp_path / "prior.json"
    current = tmp_path / "current.json"
    _write_sidecar(prior, [("KSI-SVC-SNT", "not_implemented")])
    _write_sidecar(current, [("KSI-SVC-SNT", "implemented")])

    result = runner.invoke(
        app, ["report", "diff", str(prior), str(current), "--target", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "improved:   1" in result.output


# --- error handling -------------------------------------------------------


def test_report_diff_missing_prior(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    _write_sidecar(current, [("KSI-SVC-SNT", "implemented")])
    result = runner.invoke(
        app,
        [
            "report",
            "diff",
            str(tmp_path / "missing.json"),
            str(current),
            "--target",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert "prior file not found" in result.output


def test_report_diff_missing_current(tmp_path: Path) -> None:
    prior = tmp_path / "prior.json"
    _write_sidecar(prior, [("KSI-SVC-SNT", "implemented")])
    result = runner.invoke(
        app,
        [
            "report",
            "diff",
            str(prior),
            str(tmp_path / "missing.json"),
            "--target",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert "current file not found" in result.output


def test_report_diff_invalid_json(tmp_path: Path) -> None:
    prior = tmp_path / "prior.json"
    current = tmp_path / "current.json"
    prior.write_text("not valid json {", encoding="utf-8")
    _write_sidecar(current, [("KSI-SVC-SNT", "implemented")])
    result = runner.invoke(
        app, ["report", "diff", str(prior), str(current), "--target", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "invalid JSON" in result.output


def test_report_diff_wrong_report_type(tmp_path: Path) -> None:
    """Reject non-gap-report sidecars (e.g. accidentally passing a
    documentation-{ts}.json)."""
    prior = tmp_path / "prior.json"
    current = tmp_path / "current.json"
    prior.write_text(
        json.dumps({"report_type": "documentation", "ksi_classifications": []}),
        encoding="utf-8",
    )
    _write_sidecar(current, [("KSI-SVC-SNT", "implemented")])
    result = runner.invoke(
        app, ["report", "diff", str(prior), str(current), "--target", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "expected 'gap'" in result.output


# --- subcommand registration ----------------------------------------------


def test_report_subcommand_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "report" in result.output


def test_report_diff_in_subhelp() -> None:
    result = runner.invoke(app, ["report", "--help"])
    assert result.exit_code == 0
    assert "diff" in result.output
