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
from typing import Any

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

redaction_app = typer.Typer(
    name="redaction",
    help="Inspect the LLM-prompt redaction audit log.",
    no_args_is_help=True,
)
app.add_typer(redaction_app, name="redaction")


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
    plan: Path | None = typer.Option(
        None,
        "--plan",
        help=(
            "Path to a `terraform show -json <plan>` output file. When supplied, "
            "resources are read from the resolved plan instead of parsed from .tf "
            "files — exposes module `for_each` expansion and resolved values. "
            "Mutually exclusive with HCL-directory scanning (both modes still "
            "load manifests from `--target`)."
        ),
    ),
) -> None:
    """Run all applicable detectors and load Evidence Manifests under the target.

    By default scans `.tf` files under `--target` via HCL parsing. Supply
    `--plan FILE` to instead scan a pre-generated Terraform plan JSON —
    the recommended mode for CI because module expansion and resolved
    values (jsonencode, variable references, for_each) are fully visible.
    See DECISIONS 2026-04-22 "Design: Terraform Plan JSON support" for
    the trust-posture call.
    """
    from efterlev.errors import DetectorError, ManifestError
    from efterlev.frmr.loader import FrmrDocument
    from efterlev.primitives.evidence import (
        LoadEvidenceManifestsInput,
        load_evidence_manifests,
    )
    from efterlev.primitives.scan import (
        ScanTerraformInput,
        ScanTerraformPlanInput,
        scan_terraform,
        scan_terraform_plan,
    )
    from efterlev.provenance import ProvenanceStore, active_store

    root = target.resolve()
    if not (root / ".efterlev").is_dir():
        typer.echo(
            f"error: no `.efterlev/` directory under {root}. Run `efterlev init` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    # --plan is a dedicated mode; we don't try to scan both HCL + plan in
    # the same invocation (would double-emit evidence).
    plan_path = plan.resolve() if plan is not None else None
    if plan_path is not None and not plan_path.is_file():
        typer.echo(f"error: --plan file not found: {plan_path}", err=True)
        raise typer.Exit(code=1)

    # KSI→controls mapping, derived from the cached FRMR document the workspace
    # wrote at `init` time. Required for manifest loading (we don't invent
    # control lists; we resolve them from FRMR as the single source of truth).
    # Hard-error on missing cache rather than silently skipping every manifest
    # as "unknown KSI" — the latter masked broken init states as configuration
    # mistakes. Match the error style of `agent gap`/`agent document`.
    frmr_cache = root / ".efterlev" / "cache" / "frmr_document.json"
    if not frmr_cache.is_file():
        typer.echo(
            f"error: FRMR cache missing at {frmr_cache}. Re-run `efterlev init`.",
            err=True,
        )
        raise typer.Exit(code=1)
    frmr_doc = FrmrDocument.model_validate_json(frmr_cache.read_text(encoding="utf-8"))
    ksi_to_controls: dict[str, list[str]] = {
        k: list(ind.controls) for k, ind in frmr_doc.indicators.items()
    }

    manifest_dir = root / ".efterlev" / "manifests"

    try:
        with ProvenanceStore(root) as store, active_store(store):
            if plan_path is not None:
                scan_result = scan_terraform_plan(
                    ScanTerraformPlanInput(plan_file=plan_path, target_root=root)
                )
            else:
                scan_result = scan_terraform(ScanTerraformInput(target_dir=root))
            manifest_result = load_evidence_manifests(
                LoadEvidenceManifestsInput(
                    manifest_dir=manifest_dir,
                    ksi_to_controls=ksi_to_controls,
                    scan_root=root,
                )
            )
    except (DetectorError, ManifestError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    total_evidence = scan_result.evidence_count + manifest_result.evidence_count
    scan_mode = f"plan {plan_path}" if plan_path is not None else str(root)
    typer.echo(f"Scanned {scan_mode}")
    typer.echo(f"  resources parsed:    {scan_result.resources_parsed}")
    typer.echo(f"  detectors run:       {scan_result.detectors_run}")
    typer.echo(f"  manifest files:      {manifest_result.files_found}")
    typer.echo(f"  manifests loaded:    {manifest_result.manifests_loaded}")
    typer.echo(f"  evidence records:    {total_evidence}")
    typer.echo(f"    from detectors:    {scan_result.evidence_count}")
    typer.echo(f"    from manifests:    {manifest_result.evidence_count}")
    for det in scan_result.per_detector:
        typer.echo(f"    {det.detector_id}@{det.version:<7}  +{det.evidence_count}")
    for m in manifest_result.per_manifest:
        rel = m.file.relative_to(root) if m.file.is_absolute() else m.file
        typer.echo(f"    manifest {rel}  ksi={m.ksi}  +{m.attestation_count}")
    if manifest_result.skipped_unknown_ksi:
        # Primitive already deduplicates; join for display.
        skipped = ", ".join(manifest_result.skipped_unknown_ksi)
        typer.echo(f"  skipped manifest(s) for unknown KSI(s): {skipped}")
    if scan_result.evidence_record_ids:
        typer.echo("")
        typer.echo("Detector record IDs (pass to `efterlev provenance show`):")
        for rid, ev in zip(scan_result.evidence_record_ids, scan_result.evidence, strict=False):
            # Include the short detector id so records with identical
            # resource_name across detectors (e.g. "cloudtrail" = trail,
            # bucket, SSE, backup-retention) are distinguishable in the
            # listing. Dogfood-2026-04-22 finding #6.
            short_det = ev.detector_id.split(".", 1)[1] if "." in ev.detector_id else ev.detector_id
            resource_name = ev.content.get("resource_name", "—")
            typer.echo(f"  {rid}  {short_det:<38}  {resource_name}")


@app.command()
def poam(
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the repo whose `.efterlev/` store will be read. Defaults to cwd.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help=(
            "Write the POA&M markdown to this file. "
            "Defaults to `.efterlev/reports/poam-<timestamp>.md`."
        ),
    ),
) -> None:
    """Emit a POA&M markdown for every open (partial / not_implemented) KSI.

    Reads the latest Gap Agent classifications from the provenance store,
    resolves each KSI against the loaded FRMR, and renders a POA&M
    document with a summary table and per-item detail blocks. The output
    is deterministic — same inputs produce byte-identical markdown, so
    re-running is safe and diffable.

    DRAFT — every Reviewer field in each item is emitted as a
    `DRAFT — SET BEFORE SUBMISSION` placeholder. Severity is a
    starting-point heuristic (not_implemented → HIGH, partial →
    MEDIUM); reviewer confirms per internal risk framework before
    submission.

    Suitable for paste into Jira/Linear (their markdown-paste flows
    accept tables and per-item sections) or handing to a 3PAO alongside
    the FRMR attestation JSON.
    """
    from efterlev.agents import reconstruct_classifications_from_store
    from efterlev.frmr.loader import FrmrDocument
    from efterlev.primitives.generate import (
        GeneratePoamMarkdownInput,
        PoamClassificationInput,
        generate_poam_markdown,
    )
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

    with ProvenanceStore(root) as store, active_store(store):
        rows = store.iter_claims_by_metadata_kind("ksi_classification")
        classifications = reconstruct_classifications_from_store(rows)
        if not classifications:
            typer.echo(
                "error: no Gap Agent classifications in the store. "
                "Run `efterlev agent gap` first.",
                err=True,
            )
            raise typer.Exit(code=1)

        poam_inputs = [
            PoamClassificationInput(
                ksi_id=c.ksi_id,
                status=c.status,
                rationale=c.rationale,
                evidence_ids=list(c.evidence_ids),
                claim_record_id=None,  # the reconstructed shape doesn't carry record_id
            )
            for c in classifications
        ]
        result = generate_poam_markdown(
            GeneratePoamMarkdownInput(
                classifications=poam_inputs,
                indicators=frmr_doc.indicators,
                baseline_id="fedramp-20x-moderate",
                frmr_version=frmr_doc.version,
            )
        )

    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    output_path = output or (root / ".efterlev" / "reports" / f"poam-{timestamp}.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.markdown, encoding="utf-8")

    typer.echo(f"POA&M: {output_path}")
    typer.echo(f"  open items:       {result.item_count}")
    if result.skipped_unknown_ksi:
        skipped = ", ".join(result.skipped_unknown_ksi)
        typer.echo(f"  skipped unknown:  {skipped}")


def _new_scan_id() -> str:
    """UTC-timestamped scan identifier. Used to tag redaction-ledger entries
    so a user can later run `efterlev redaction review --scan-id <ts>` to see
    what got redacted on a specific run. Filesystem-safe, second-resolution
    (race-safe for typical operator cadence).
    """
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")


def _write_scan_redaction_log(ledger_obj: Any, root: Path, scan_id: str) -> None:
    """Dump a RedactionLedger to `.efterlev/redacted.log` and echo a summary.

    The log is opened with 0600 perms at create time and re-chmodded to
    0600 on every append. An empty ledger is a no-op. See DECISIONS
    2026-04-23 "Redaction audit log + review CLI" for the full design.
    """
    from efterlev.llm.scrubber import write_redaction_log

    count = write_redaction_log(
        ledger_obj, root / ".efterlev" / "redacted.log", scan_id=scan_id
    )
    if count > 0:
        pattern_counts = ledger_obj.pattern_counts()
        summary = ", ".join(f"{n}x{name}" for name, n in sorted(pattern_counts.items()))
        typer.echo(
            f"Redacted {count} secret(s) from prompt content ({summary}); "
            f"audit: `efterlev redaction review --scan-id {scan_id}`."
        )


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
    from efterlev.llm.scrubber import RedactionLedger, active_redaction_ledger
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

    scan_id = _new_scan_id()
    ledger = RedactionLedger()

    try:
        with ProvenanceStore(root) as store:
            evidence = [Evidence.model_validate(p) for _rid, p in store.iter_evidence()]
            if not evidence:
                typer.echo(
                    "error: no evidence records in the store. Run `efterlev scan` first.",
                    err=True,
                )
                raise typer.Exit(code=1)

            with active_store(store), active_redaction_ledger(ledger):
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
        evidence=evidence,
    )
    reports_dir = root / ".efterlev" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    html_path = reports_dir / f"gap-{timestamp}.html"
    html_path.write_text(html_body, encoding="utf-8")
    typer.echo("")
    typer.echo(f"HTML report: {html_path}")

    _write_scan_redaction_log(ledger, root, scan_id)


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
    from efterlev.llm.scrubber import RedactionLedger, active_redaction_ledger
    from efterlev.models import Evidence
    from efterlev.primitives.generate import (
        GenerateFrmrAttestationInput,
        generate_frmr_attestation,
    )
    from efterlev.provenance import ProvenanceStore, active_store
    from efterlev.reports import render_documentation_report_html

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

    # Single ProvenanceStore context for the whole command: agent invocation
    # and FRMR-attestation generation both write records, and both belong to
    # the same logical "documentation run" in the provenance graph. Opening
    # the store twice (as this command did before Phase 2 polish) would put
    # the two primitives' records in different active-store contexts, which
    # is observable through the provenance walker and wasted SQLite opens.
    scan_id = _new_scan_id()
    ledger = RedactionLedger()

    try:
        with (
            ProvenanceStore(root) as store,
            active_store(store),
            active_redaction_ledger(ledger),
        ):
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

            attestation_drafts = [att.draft for att in report.attestations]
            claim_record_ids = {
                att.draft.ksi_id: att.claim_record_id
                for att in report.attestations
                if att.claim_record_id is not None
            }
            attestation_result = generate_frmr_attestation(
                GenerateFrmrAttestationInput(
                    drafts=attestation_drafts,
                    indicators=frmr_doc.indicators,
                    baseline_id="fedramp-20x-moderate",
                    frmr_version=frmr_doc.version,
                    frmr_last_updated=frmr_doc.last_updated,
                    claim_record_ids=claim_record_ids,
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

    # FRMR-compatible attestation JSON alongside the HTML — one CLI run, two
    # artifacts. The human-readable HTML is for review; the machine-readable
    # JSON is the v1 primary production output fed to 3PAOs and downstream.
    attestation_path = reports_dir / f"attestation-{timestamp}.json"
    attestation_path.write_text(attestation_result.artifact_json, encoding="utf-8")
    typer.echo(f"FRMR attestation: {attestation_path}")
    typer.echo(f"  indicators:       {attestation_result.indicator_count}")
    if attestation_result.skipped_unknown_ksi:
        # Primitive already deduplicates; just format for display.
        skipped = ", ".join(attestation_result.skipped_unknown_ksi)
        typer.echo(f"  skipped unknown:  {skipped}")

    _write_scan_redaction_log(ledger, root, scan_id)


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
    from efterlev.llm.scrubber import RedactionLedger, active_redaction_ledger
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

    scan_id = _new_scan_id()
    ledger = RedactionLedger()

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

            # Manifest-sourced Evidence is human-signed procedural attestation;
            # a manifest YAML is NOT Terraform source, so reading it as source
            # for the Remediation Agent would produce nonsense diffs. The
            # agent still sees the manifest evidence in its prompt (so it can
            # reason "this KSI has attestations plus a Terraform gap"); we
            # just don't load the YAML contents as `.tf` source.
            from efterlev.primitives.evidence import MANIFEST_DETECTOR_ID

            terraform_evidence = [
                ev for ev in ksi_evidence if ev.detector_id != MANIFEST_DETECTOR_ID
            ]

            # If every Evidence for this KSI is manifest-sourced, there is no
            # Terraform surface for the agent to remediate. That's not an
            # error — the customer has attested procedurally, but the scanner
            # found no infra-layer gap to fix. Exit cleanly with a clear
            # message. This is the common case when a KSI is `partial` and
            # the gap is purely procedural (documentation, process, or SOP).
            if not terraform_evidence:
                typer.echo(
                    f"{ksi} has only manifest-sourced evidence ({len(ksi_evidence)} "
                    f"attestation(s)); no Terraform surface to remediate. The "
                    f"procedural gap — if any — is addressed by updating the "
                    f"manifest(s) under .efterlev/manifests/, not by a .tf diff."
                )
                raise typer.Exit(code=0)

            # Read the .tf files every Terraform-sourced evidence record
            # points at, keyed by the path as stored in the evidence.
            # `resolve_within_root` joins against `root` and rejects any
            # resolved path that escapes containment, so a hostile evidence
            # record cannot exfiltrate arbitrary files.
            from efterlev.paths import resolve_within_root

            source_files: dict[str, str] = {}
            for ev in terraform_evidence:
                rel_path = Path(str(ev.source_ref.file))
                # Non-.tf files (e.g. the plan JSON in plan-mode scans where
                # root-module resources land with `source_ref.file` pointing
                # at the plan file itself) are skipped here — a diff against
                # generated JSON doesn't change infrastructure. Fallback
                # below loads the .tf tree under target_root so the agent
                # still has source to reason about. Dogfood-2026-04-22
                # plan-mode finding.
                if rel_path.suffix != ".tf":
                    continue
                full = resolve_within_root(rel_path, root)
                if full is None or not full.is_file():
                    continue
                key = str(ev.source_ref.file)
                if key not in source_files:
                    source_files[key] = full.read_text(encoding="utf-8")

            # Plan-mode fallback: root-module resources' source_refs point
            # at the plan JSON, not the owning .tf file, because plan JSON
            # doesn't carry per-resource file info (only module-call
            # `source` hints). When evidence-walk produced no loadable .tf
            # content, sweep target_root for .tf files so the agent sees
            # the actual infrastructure source rather than refusing with
            # "no terraform surface to remediate" on a file that IS there.
            if not source_files:
                for tf_path in sorted(root.rglob("*.tf")):
                    # Skip anything inside .efterlev/ (tool state) or
                    # vendor-y hidden dirs. `relative_to(root)` preserves
                    # the repo-relative-path contract.
                    if any(part.startswith(".") for part in tf_path.relative_to(root).parts):
                        continue
                    rel = str(tf_path.relative_to(root))
                    source_files[rel] = tf_path.read_text(encoding="utf-8")

            with active_store(store), active_redaction_ledger(ledger):
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

    html_body = render_remediation_proposal_html(proposal, evidence=ksi_evidence)
    reports_dir = root / ".efterlev" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    # Include the KSI in the filename so running remediate for multiple KSIs
    # doesn't produce files that can only be distinguished by timestamp.
    html_path = reports_dir / f"remediation-{ksi}-{timestamp}.html"
    html_path.write_text(html_body, encoding="utf-8")
    typer.echo("")
    typer.echo(f"HTML report: {html_path}")

    _write_scan_redaction_log(ledger, root, scan_id)


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


@redaction_app.command("review")
def redaction_review(
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the repo whose `.efterlev/redacted.log` to read. Defaults to cwd.",
    ),
    scan_id: str | None = typer.Option(
        None,
        "--scan-id",
        help="Show only redactions from a specific scan-id (e.g. 20260423T163045).",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        help="Maximum number of recent scans to summarize. Only applies when --scan-id is not set.",
    ),
) -> None:
    """Summarize the redaction audit log written during agent runs.

    Every agent invocation (`efterlev agent gap`, `document`, `remediate`)
    opens a `RedactionLedger` context that captures every secret the
    scrubber removed from a prompt. The ledger is appended to
    `.efterlev/redacted.log` (JSONL, 0600 perms). This command reads the
    log and prints a per-scan summary: how many secrets of which kinds
    were redacted in each scan, in field-location terms (NOT the secrets
    themselves — the log is audit-safe and never writes secret material).

    Without `--scan-id`, shows the most recent `limit` scans. With
    `--scan-id`, drills into one scan's events.
    """
    import json

    root = target.resolve()
    log_path = root / ".efterlev" / "redacted.log"
    if not log_path.is_file():
        typer.echo(
            f"No redaction log at {log_path}. "
            f"This means either no agent has run under this target, or no "
            f"redactions have occurred during any run.",
        )
        raise typer.Exit(code=0)

    # Load events, grouped by scan_id, in the order they appear.
    by_scan: dict[str, list[dict]] = {}
    scan_order: list[str] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines rather than abort — audit log integrity
                # isn't cryptographically enforced, only perm-enforced.
                continue
            sid = record.get("scan_id", "<unknown>")
            if sid not in by_scan:
                by_scan[sid] = []
                scan_order.append(sid)
            by_scan[sid].append(record)

    if scan_id is not None:
        events = by_scan.get(scan_id)
        if events is None:
            typer.echo(f"No redactions recorded for scan-id {scan_id!r}.")
            raise typer.Exit(code=1)
        typer.echo(f"Scan {scan_id} — {len(events)} redactions:")
        for ev in events:
            typer.echo(
                f"  {ev['timestamp']}  {ev['pattern_name']:<28}  "
                f"sha256:{ev['sha256_prefix']}  @ {ev['context_hint']}"
            )
        return

    # Default: per-scan summary, most recent `limit` scans.
    recent = scan_order[-limit:]
    typer.echo(f"Redaction audit log: {log_path} ({len(scan_order)} scan(s) total)")
    typer.echo("")
    typer.echo(f"{'scan_id':<18}  {'n':>4}  pattern counts")
    for sid in recent:
        events = by_scan[sid]
        counts: dict[str, int] = {}
        for ev in events:
            counts[ev["pattern_name"]] = counts.get(ev["pattern_name"], 0) + 1
        summary = ", ".join(f"{n}x{name}" for name, n in sorted(counts.items()))
        typer.echo(f"{sid:<18}  {len(events):>4}  {summary}")
    if len(scan_order) > limit:
        typer.echo(f"... {len(scan_order) - limit} earlier scan(s) not shown (--limit).")
    typer.echo("")
    typer.echo("Run `efterlev redaction review --scan-id <id>` for per-event detail.")


if __name__ == "__main__":
    app()
