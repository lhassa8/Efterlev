"""CLI shape tests.

Verifies the CLI registers every v0 subcommand, that `--help` / `--version` work,
and that stub subcommands raise `NotImplementedError`. Does not yet exercise any
real behavior — that lands with each subcommand's implementation phase.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from efterlev import __version__
from efterlev.cli.main import app

runner = CliRunner()


def test_root_help_lists_every_v0_subcommand() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("init", "scan", "agent", "provenance", "mcp"):
        assert cmd in result.output


def test_version_flag_prints_package_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_agent_subtree_lists_three_agents() -> None:
    result = runner.invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    for sub in ("gap", "document", "remediate"):
        assert sub in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["init"],
        ["scan"],
        ["agent", "gap"],
        ["agent", "document", "--ksi", "KSI-SVC-SNT"],
        ["agent", "remediate", "--ksi", "KSI-SVC-SNT"],
        ["provenance", "show", "deadbeef"],
        ["mcp", "serve"],
    ],
    ids=lambda args: " ".join(args),
)
def test_subcommand_stubs_raise_not_implemented(args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert isinstance(result.exception, NotImplementedError)
    # The stub message should name the phase so the user knows what's coming.
    assert "Phase" in str(result.exception)


def test_remediate_requires_ksi_option() -> None:
    result = runner.invoke(app, ["agent", "remediate"])
    # Missing required --ksi should fail at Typer's argument parser (exit 2),
    # not reach the stub body.
    assert result.exit_code == 2
    assert result.exception is None or not isinstance(result.exception, NotImplementedError)
