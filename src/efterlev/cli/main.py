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

from datetime import datetime
from pathlib import Path

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
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the repo to initialize. Defaults to the current directory.",
    ),
    baseline: str = typer.Option(
        "fedramp-20x-moderate",
        "--baseline",
        help="Compliance baseline to load. v0 supports `fedramp-20x-moderate` only.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing `.efterlev/` directory.",
    ),
) -> None:
    """Initialize `.efterlev/` in the target repo with a provenance store and config."""
    from efterlev.errors import CatalogLoadError, ConfigError
    from efterlev.workspace import init_workspace

    try:
        result = init_workspace(target.resolve(), baseline, force=force)
    except (ConfigError, CatalogLoadError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"Initialized {result.efterlev_dir}")
    typer.echo(f"  baseline:              {result.baseline}")
    typer.echo(
        f"  FRMR:                  v{result.frmr_version} "
        f"({result.frmr_last_updated}, {result.num_themes} themes, "
        f"{result.num_indicators} indicators)"
    )
    typer.echo(
        f"  NIST SP 800-53 Rev 5:  "
        f"{result.num_controls} controls "
        f"(+{result.num_enhancements} enhancements)"
    )
    typer.echo(f"  load receipt:          {result.receipt_record_id}")


@app.command()
def scan(
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the repo to scan. Defaults to the current directory.",
    ),
) -> None:
    """Run all applicable detectors against the target and write evidence records."""
    from efterlev.errors import DetectorError
    from efterlev.primitives.scan import ScanTerraformInput, scan_terraform
    from efterlev.provenance import ProvenanceStore, active_store

    root = target.resolve()
    if not (root / ".efterlev").is_dir():
        typer.echo(
            f"error: no `.efterlev/` directory under {root}. Run `efterlev init` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        with ProvenanceStore(root) as store, active_store(store):
            result = scan_terraform(ScanTerraformInput(target_dir=root))
    except DetectorError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"Scanned {root}")
    typer.echo(f"  resources parsed:  {result.resources_parsed}")
    typer.echo(f"  detectors run:     {result.detectors_run}")
    typer.echo(f"  evidence records:  {result.evidence_count}")
    for det in result.per_detector:
        typer.echo(f"    {det.detector_id}@{det.version:<7}  +{det.evidence_count}")
    if result.evidence_record_ids:
        typer.echo("")
        typer.echo("Record IDs (pass to `efterlev provenance show`):")
        for rid, ev in zip(result.evidence_record_ids, result.evidence, strict=False):
            typer.echo(f"  {rid}  {ev.content.get('resource_name', '—')}")


@agent_app.command("gap")
def agent_gap(
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the repo whose `.efterlev/` store will be read. Defaults to cwd.",
    ),
) -> None:
    """Classify each KSI as implemented / partial / not implemented / NA."""
    from efterlev.agents import GapAgent, GapAgentInput
    from efterlev.errors import AgentError
    from efterlev.frmr.loader import FrmrDocument
    from efterlev.models import Evidence
    from efterlev.provenance import ProvenanceStore, active_store

    root = target.resolve()
    if not (root / ".efterlev").is_dir():
        typer.echo(
            f"error: no `.efterlev/` directory under {root}. Run `efterlev init` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    frmr_cache = root / ".efterlev" / "cache" / "frmr_document.json"
    if not frmr_cache.is_file():
        typer.echo(
            f"error: FRMR cache missing at {frmr_cache}. Re-run `efterlev init`.",
            err=True,
        )
        raise typer.Exit(code=1)

    frmr_doc = FrmrDocument.model_validate_json(frmr_cache.read_text(encoding="utf-8"))
    indicators = list(frmr_doc.indicators.values())

    try:
        with ProvenanceStore(root) as store:
            evidence = [Evidence.model_validate(p) for _rid, p in store.iter_evidence()]
            if not evidence:
                typer.echo(
                    "error: no evidence records in the store. Run `efterlev scan` first.",
                    err=True,
                )
                raise typer.Exit(code=1)

            with active_store(store):
                agent = GapAgent()
                report = agent.run(GapAgentInput(indicators=indicators, evidence=evidence))
    except AgentError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"Gap Agent classified {len(report.ksi_classifications)} KSI(s).")
    for clf in report.ksi_classifications:
        typer.echo(f"  {clf.ksi_id:<14}  {clf.status}")
        typer.echo(f"                  {clf.rationale}")
    if report.unmapped_findings:
        typer.echo("")
        typer.echo(f"Unmapped findings ({len(report.unmapped_findings)}):")
        for um in report.unmapped_findings:
            typer.echo(f"  {um.evidence_id}  controls={','.join(um.controls)}")
            typer.echo(f"    {um.note}")
    if report.claim_record_ids:
        typer.echo("")
        typer.echo("Claim record IDs (pass to `efterlev provenance show`):")
        for cid in report.claim_record_ids:
            typer.echo(f"  {cid}")

    from efterlev.reports import render_gap_report_html

    html_body = render_gap_report_html(
        report,
        baseline_id="fedramp-20x-moderate",
        frmr_version=frmr_doc.version,
    )
    reports_dir = root / ".efterlev" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    html_path = reports_dir / f"gap-{timestamp}.html"
    html_path.write_text(html_body, encoding="utf-8")
    typer.echo("")
    typer.echo(f"HTML report: {html_path}")


@agent_app.command("document")
def agent_document(
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the repo whose `.efterlev/` store will be read. Defaults to cwd.",
    ),
    ksi: str = typer.Option(
        None,
        "--ksi",
        help="KSI ID to draft an attestation for. Defaults to every classified KSI.",
    ),
) -> None:
    """Draft an FRMR-compatible attestation for a KSI, grounded in its evidence."""
    from efterlev.agents import (
        DocumentationAgent,
        DocumentationAgentInput,
        reconstruct_classifications_from_store,
    )
    from efterlev.errors import AgentError
    from efterlev.frmr.loader import FrmrDocument
    from efterlev.models import Evidence
    from efterlev.provenance import ProvenanceStore, active_store

    root = target.resolve()
    if not (root / ".efterlev").is_dir():
        typer.echo(
            f"error: no `.efterlev/` directory under {root}. Run `efterlev init` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    frmr_cache = root / ".efterlev" / "cache" / "frmr_document.json"
    if not frmr_cache.is_file():
        typer.echo(
            f"error: FRMR cache missing at {frmr_cache}. Re-run `efterlev init`.",
            err=True,
        )
        raise typer.Exit(code=1)

    frmr_doc = FrmrDocument.model_validate_json(frmr_cache.read_text(encoding="utf-8"))

    try:
        with ProvenanceStore(root) as store:
            evidence = [Evidence.model_validate(p) for _rid, p in store.iter_evidence()]
            classification_rows = store.iter_claims_by_metadata_kind("ksi_classification")
            classifications = reconstruct_classifications_from_store(classification_rows)

            if not classifications:
                typer.echo(
                    "error: no Gap Agent classifications in the store. "
                    "Run `efterlev agent gap` first.",
                    err=True,
                )
                raise typer.Exit(code=1)

            with active_store(store):
                agent = DocumentationAgent()
                report = agent.run(
                    DocumentationAgentInput(
                        indicators=frmr_doc.indicators,
                        evidence=evidence,
                        classifications=classifications,
                        baseline_id="fedramp-20x-moderate",
                        frmr_version=frmr_doc.version,
                        only_ksi=ksi,
                    )
                )
    except AgentError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"Documentation Agent drafted {len(report.attestations)} attestation(s).")
    for att in report.attestations:
        draft = att.draft
        typer.echo("")
        typer.echo(f"  === {draft.ksi_id} ({draft.status or 'no status'}) ===")
        typer.echo(f"  citations: {len(draft.citations)}")
        if draft.narrative:
            # Wrap-free first 160 chars as a preview; full draft lives in the store.
            preview = draft.narrative.strip().replace("\n", " ")
            ellipsis = "…" if len(preview) > 160 else ""
            typer.echo(f"  DRAFT — requires human review: {preview[:160]}{ellipsis}")
        if att.claim_record_id is not None:
            typer.echo(f"  record id: {att.claim_record_id}")
    if report.skipped_ksi_ids:
        typer.echo("")
        skipped = ", ".join(report.skipped_ksi_ids)
        typer.echo(f"Skipped {len(report.skipped_ksi_ids)} KSI(s): {skipped}")

    from efterlev.reports import render_documentation_report_html

    html_body = render_documentation_report_html(
        report,
        baseline_id="fedramp-20x-moderate",
        frmr_version=frmr_doc.version,
    )
    reports_dir = root / ".efterlev" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    html_path = reports_dir / f"documentation-{timestamp}.html"
    html_path.write_text(html_body, encoding="utf-8")
    typer.echo("")
    typer.echo(f"HTML report: {html_path}")


@agent_app.command("remediate")
def agent_remediate(
    ksi: str = typer.Option(
        ...,
        "--ksi",
        help="KSI ID to propose a remediation for.",
    ),
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the repo whose `.efterlev/` store will be read. Defaults to cwd.",
    ),
) -> None:
    """Propose a Terraform diff fixing a selected KSI gap."""
    from efterlev.agents import (
        RemediationAgent,
        RemediationAgentInput,
        reconstruct_classifications_from_store,
    )
    from efterlev.errors import AgentError
    from efterlev.frmr.loader import FrmrDocument
    from efterlev.models import Evidence
    from efterlev.provenance import ProvenanceStore, active_store

    root = target.resolve()
    if not (root / ".efterlev").is_dir():
        typer.echo(
            f"error: no `.efterlev/` directory under {root}. Run `efterlev init` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    frmr_cache = root / ".efterlev" / "cache" / "frmr_document.json"
    if not frmr_cache.is_file():
        typer.echo(
            f"error: FRMR cache missing at {frmr_cache}. Re-run `efterlev init`.",
            err=True,
        )
        raise typer.Exit(code=1)

    frmr_doc = FrmrDocument.model_validate_json(frmr_cache.read_text(encoding="utf-8"))
    indicator = frmr_doc.indicators.get(ksi)
    if indicator is None:
        typer.echo(
            f"error: KSI {ksi!r} is not in the loaded baseline (FRMR {frmr_doc.version}).",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        with ProvenanceStore(root) as store:
            classification_rows = store.iter_claims_by_metadata_kind("ksi_classification")
            classifications = reconstruct_classifications_from_store(classification_rows)
            clf = next((c for c in classifications if c.ksi_id == ksi), None)
            if clf is None:
                typer.echo(
                    f"error: no Gap Agent classification for {ksi} in the store. "
                    "Run `efterlev agent gap` first.",
                    err=True,
                )
                raise typer.Exit(code=1)
            if clf.status == "implemented":
                typer.echo(f"{ksi} is classified as `implemented`. No remediation needed.")
                raise typer.Exit(code=0)
            if clf.status == "not_applicable":
                typer.echo(f"{ksi} is classified as `not_applicable`. No remediation needed.")
                raise typer.Exit(code=0)

            all_evidence = [Evidence.model_validate(p) for _rid, p in store.iter_evidence()]
            ksi_evidence = [ev for ev in all_evidence if ksi in ev.ksis_evidenced]

            # Read the .tf files every evidence record points at, keyed by
            # the path as stored in the evidence (typically repo-relative).
            # `resolve_within_root` rejects absolute paths and `..` traversal
            # so a hostile evidence record cannot exfiltrate arbitrary files
            # from the host.
            from efterlev.paths import resolve_within_root

            source_files: dict[str, str] = {}
            for ev in ksi_evidence:
                rel_path = Path(str(ev.source_ref.file))
                full = resolve_within_root(rel_path, root)
                if full is None or not full.is_file():
                    continue
                key = str(ev.source_ref.file)
                if key not in source_files:
                    source_files[key] = full.read_text(encoding="utf-8")

            with active_store(store):
                agent = RemediationAgent()
                proposal = agent.run(
                    RemediationAgentInput(
                        indicator=indicator,
                        classification=clf,
                        evidence=ksi_evidence,
                        source_files=source_files,
                        baseline_id="fedramp-20x-moderate",
                        frmr_version=frmr_doc.version,
                    )
                )
    except AgentError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"Remediation Agent draft for {proposal.ksi_id} ({proposal.status}):")
    typer.echo("")
    typer.echo("DRAFT — requires human review. Efterlev does not apply diffs.")
    typer.echo("")
    typer.echo(proposal.explanation)
    if proposal.diff:
        typer.echo("")
        typer.echo("--- diff ---")
        typer.echo(proposal.diff)
    if proposal.cited_source_files:
        typer.echo("")
        typer.echo(f"Files touched: {', '.join(proposal.cited_source_files)}")
    if proposal.claim_record_id is not None:
        typer.echo("")
        typer.echo(f"record id: {proposal.claim_record_id}")

    from efterlev.reports import render_remediation_proposal_html

    html_body = render_remediation_proposal_html(proposal)
    reports_dir = root / ".efterlev" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    # Include the KSI in the filename so running remediate for multiple KSIs
    # doesn't produce files that can only be distinguished by timestamp.
    html_path = reports_dir / f"remediation-{ksi}-{timestamp}.html"
    html_path.write_text(html_body, encoding="utf-8")
    typer.echo("")
    typer.echo(f"HTML report: {html_path}")


@provenance_app.command("show")
def provenance_show(
    record_id: str = typer.Argument(..., help="SHA-256 record ID to walk."),
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Repo containing the `.efterlev/` store. Defaults to the current directory.",
    ),
) -> None:
    """Walk the provenance chain from a record back to its source lines."""
    from efterlev.errors import ProvenanceError
    from efterlev.provenance import ProvenanceStore, render_chain_text, walk_chain

    root = target.resolve()
    if not (root / ".efterlev").is_dir():
        typer.echo(
            f"error: no `.efterlev/` directory under {root}. Run `efterlev init` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        with ProvenanceStore(root) as store:
            tree = walk_chain(store, record_id)
            typer.echo(render_chain_text(tree))
    except ProvenanceError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e


@mcp_app.command("serve")
def mcp_serve() -> None:
    """Run the MCP stdio server exposing every registered tool.

    Blocks on stdin/stdout for the MCP protocol. Intended to be launched
    as a subprocess by an MCP client (Claude Code, etc.); not interactive.
    Per DECISIONS design call #4: stdio-only, stateless, every tool call
    logged to the target repo's provenance store for audit.
    """
    import asyncio

    from efterlev.mcp_server import run_stdio_server

    try:
        asyncio.run(run_stdio_server())
    except KeyboardInterrupt:
        # Clean shutdown on Ctrl-C; Typer already swallows but be explicit.
        raise typer.Exit(code=0) from None


if __name__ == "__main__":
    app()
