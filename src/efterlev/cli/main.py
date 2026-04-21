"""Efterlev CLI entry point.

The `app` Typer instance is the package's script entry (declared in
`pyproject.toml` as `efterlev = "efterlev.cli.main:app"`). Every subcommand
is a stub that raises `NotImplementedError` naming which build phase will
implement it. The CLI's *shape* is stable from Phase 0 onward; callers and
downstream scripts can depend on command and option names without waiting
for behavior to land.

Implementation phases (see `docs/dual_horizon_plan.md` §2.3):

  Phase 0  scaffold this CLI (done)
  Phase 1  models + primitives + provenance store/walker
  Phase 2  catalog loaders (FRMR + 800-53), `init`, first detector, `scan`
  Phase 3  Gap / Documentation / Remediation agents, FRMR generator
  Phase 4  MCP server wiring, demo polish
"""

from __future__ import annotations

import typer

from efterlev import __version__

app = typer.Typer(
    name="efterlev",
    help="Repo-native, agent-first compliance scanner for FedRAMP 20x and DoD IL.",
    add_completion=False,
)

agent_app = typer.Typer(
    name="agent",
    help="Run a reasoning agent (Gap, Documentation, or Remediation).",
    no_args_is_help=True,
)
app.add_typer(agent_app, name="agent")

provenance_app = typer.Typer(
    name="provenance",
    help="Inspect the local provenance graph.",
    no_args_is_help=True,
)
app.add_typer(provenance_app, name="provenance")

mcp_app = typer.Typer(
    name="mcp",
    help="Expose Efterlev's primitives over an MCP stdio server.",
    no_args_is_help=True,
)
app.add_typer(mcp_app, name="mcp")


def _stub(phase: str, command: str) -> None:
    """Raise a stub error with a clear phase pointer.

    Used by every Phase-0 subcommand callback so the CLI shape is real but
    behavior is deferred to the phase that will implement it. See the module
    docstring for the phase map.
    """
    raise NotImplementedError(
        f"`efterlev {command}` is a stub in v{__version__}; "
        f"scheduled for Phase {phase}. See docs/dual_horizon_plan.md §2.3."
    )


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Print the Efterlev version and exit.",
        is_eager=True,
    ),
) -> None:
    """Efterlev root callback. Handles --version and the no-subcommand case."""
    if version:
        typer.echo(f"efterlev {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def init(
    target: str = typer.Option(
        ".",
        "--target",
        help="Path to the repo to scan. Defaults to the current directory.",
    ),
    baseline: str = typer.Option(
        "fedramp-20x-moderate",
        "--baseline",
        help="Compliance baseline to load. v0 supports `fedramp-20x-moderate` only.",
    ),
) -> None:
    """Initialize `.efterlev/` in the target repo with a provenance store and config."""
    _stub("2", "init")


@app.command()
def scan(
    target: str = typer.Option(
        ".",
        "--target",
        help="Path to the repo to scan. Defaults to the current directory.",
    ),
) -> None:
    """Run all applicable detectors against the target and write evidence records."""
    _stub("2", "scan")


@agent_app.command("gap")
def agent_gap() -> None:
    """Classify each KSI as implemented / partial / not implemented / NA."""
    _stub("3", "agent gap")


@agent_app.command("document")
def agent_document(
    ksi: str = typer.Option(
        None,
        "--ksi",
        help="KSI ID to draft an attestation for. Defaults to all implemented KSIs.",
    ),
) -> None:
    """Draft an FRMR-compatible attestation for a KSI, grounded in its evidence."""
    _stub("3", "agent document")


@agent_app.command("remediate")
def agent_remediate(
    ksi: str = typer.Option(
        ...,
        "--ksi",
        help="KSI ID to propose a remediation for.",
    ),
) -> None:
    """Propose a Terraform diff fixing a selected KSI gap."""
    _stub("3", "agent remediate")


@provenance_app.command("show")
def provenance_show(
    record_id: str = typer.Argument(..., help="SHA-256 record ID to walk."),
) -> None:
    """Walk the provenance chain from a record back to its source lines."""
    _stub("1", "provenance show")


@mcp_app.command("serve")
def mcp_serve() -> None:
    """Run the MCP stdio server exposing every registered primitive."""
    _stub("4", "mcp serve")


if __name__ == "__main__":
    app()
