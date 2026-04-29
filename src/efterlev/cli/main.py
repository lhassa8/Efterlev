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

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import typer

from efterlev import __version__
from efterlev.cli.friendly_errors import friendly_llm_error_handler

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

detectors_app = typer.Typer(
    name="detectors",
    help="Inspect the registered detector library.",
    no_args_is_help=True,
)
app.add_typer(detectors_app, name="detectors")

boundary_app = typer.Typer(
    name="boundary",
    help="Declare and inspect the FedRAMP authorization boundary scope.",
    no_args_is_help=True,
)
app.add_typer(boundary_app, name="boundary")

report_app = typer.Typer(
    name="report",
    help="Operate on prior gap-report artifacts (diff, etc.).",
    no_args_is_help=True,
)
app.add_typer(report_app, name="report")


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


def _display_path(p: Path, target: Path) -> str:
    # On macOS, `/tmp` is a symlink to `/private/tmp`. We resolve target
    # paths internally so provenance records carry canonical paths, but
    # users typing `--target /tmp/X` then hunting for `/private/tmp/...`
    # in their finder is a real paper-cut. Re-stitch the path under the
    # un-resolved target form for display only. Falls back to the
    # canonical path if `p` isn't actually under `target.resolve()`.
    try:
        return str(target / p.relative_to(target.resolve()))
    except ValueError:
        return str(p)


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
    llm_backend: str = typer.Option(
        "anthropic",
        "--llm-backend",
        help="LLM backend: 'anthropic' (direct API) or 'bedrock' (AWS Bedrock).",
    ),
    llm_region: str | None = typer.Option(
        None,
        "--llm-region",
        help=(
            "AWS region for Bedrock backend (e.g. 'us-gov-west-1'). "
            "Required when --llm-backend=bedrock."
        ),
    ),
    llm_model: str | None = typer.Option(
        None,
        "--llm-model",
        help=(
            "LLM model ID. When omitted, each agent uses its per-task "
            "default (Opus 4.7 for Gap and Remediation; Sonnet 4.6 for "
            "Documentation, ~5x cheaper for narrative drafting). When "
            "set, every agent uses this model uniformly. Bedrock backend "
            "always populates a Bedrock-shaped ID (e.g. "
            "'us.anthropic.claude-opus-4-7-v1:0')."
        ),
    ),
) -> None:
    """Initialize `.efterlev/` in the target repo with a provenance store and config."""
    from efterlev.config import DEFAULT_BEDROCK_MODEL, LLMConfig
    from efterlev.errors import CatalogLoadError, ConfigError
    from efterlev.workspace import init_workspace

    # Typer-level validation: fail fast on obvious CLI mistakes before
    # Pydantic's model_validator catches the same thing at config construction.
    if llm_backend not in ("anthropic", "bedrock"):
        typer.echo(
            f"error: --llm-backend must be 'anthropic' or 'bedrock', got {llm_backend!r}",
            err=True,
        )
        raise typer.Exit(code=2)
    if llm_backend == "bedrock" and not llm_region:
        typer.echo(
            "error: --llm-region is required when --llm-backend=bedrock "
            "(e.g. 'us-gov-west-1' or 'us-east-1')",
            err=True,
        )
        raise typer.Exit(code=2)
    if llm_backend == "anthropic" and llm_region:
        typer.echo(
            "error: --llm-region is only valid with --llm-backend=bedrock",
            err=True,
        )
        raise typer.Exit(code=2)

    # Build LLMConfig explicitly so the Pydantic validator enforces the
    # invariants one more time (defense in depth).
    #
    # Anthropic backend: when --llm-model is not passed, store None so the
    # per-agent default_model values (Sonnet for Documentation, Opus for
    # Gap and Remediation) stay live at agent runtime. Passing --llm-model
    # at init overrides every agent's default uniformly.
    #
    # Bedrock backend: always populate model with a Bedrock-shaped ID
    # because the per-agent default_model values use Anthropic short-form
    # IDs that Bedrock does not accept. The LLMConfig validator rejects
    # `backend=bedrock, model=None` to enforce this.
    if llm_backend == "bedrock":
        configured_model: str | None = llm_model or DEFAULT_BEDROCK_MODEL
    else:
        configured_model = llm_model
    llm_config = LLMConfig(
        backend=llm_backend,  # type: ignore[arg-type]
        model=configured_model,
        region=llm_region,
    )

    # Priority 3.4 (2026-04-28): show the first-run wizard before init
    # touches disk. Auto-skips on non-TTY (CI-safe) and when credentials
    # are already configured. The wizard only prints; it never blocks
    # init, so CI and scripted-init flows behave identically.
    from efterlev.cli.first_run_wizard import maybe_show_first_run_intro

    maybe_show_first_run_intro(llm_backend=llm_backend)

    try:
        result = init_workspace(
            target.resolve(),
            baseline,
            force=force,
            llm_config=llm_config,
        )
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
    from efterlev.boundary import active_boundary_config
    from efterlev.config import load_config
    from efterlev.errors import ConfigError, DetectorError, ManifestError
    from efterlev.frmr.loader import FrmrDocument
    from efterlev.primitives.evidence import (
        LoadEvidenceManifestsInput,
        load_evidence_manifests,
    )
    from efterlev.primitives.scan import (
        ScanGithubWorkflowsInput,
        ScanTerraformInput,
        ScanTerraformPlanInput,
        scan_github_workflows,
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

    # Priority 4 (2026-04-27): activate the workspace's `[boundary]` config so
    # detectors emit Evidence with the correct `boundary_state`. Empty boundary
    # is the default ("boundary_undeclared") — the user hasn't told us their
    # FedRAMP scope, so every Evidence flows through unfiltered.
    try:
        workspace_config = load_config(root / ".efterlev" / "config.toml")
    except ConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        with (
            ProvenanceStore(root) as store,
            active_store(store),
            active_boundary_config(workspace_config.boundary),
        ):
            if plan_path is not None:
                scan_result = scan_terraform_plan(
                    ScanTerraformPlanInput(plan_file=plan_path, target_root=root)
                )
            else:
                scan_result = scan_terraform(ScanTerraformInput(target_dir=root))
            # Priority 1.2 (2026-04-27): also scan `.github/workflows/*.yml`
            # for repo-metadata detectors (currently github.ci_validation_gates
            # for KSI-CMT-VTD). Empty result when the target has no
            # `.github/workflows/` directory — typical for non-GitHub-Actions
            # repos. Both terraform and github-workflows results merge into
            # the user-facing scan summary.
            workflow_result = scan_github_workflows(ScanGithubWorkflowsInput(target_dir=root))
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

    total_evidence = (
        scan_result.evidence_count + workflow_result.evidence_count + manifest_result.evidence_count
    )
    scan_mode = f"plan {plan_path}" if plan_path is not None else str(root)
    typer.echo(f"Scanned {scan_mode}")
    typer.echo(f"  resources parsed:    {scan_result.resources_parsed}")
    if scan_result.module_calls > 0:
        # Surfaced alongside resources so the imbalance (5 resources / 11
        # module calls) is visible at the top of the summary, not buried.
        typer.echo(f"  module calls:        {scan_result.module_calls}")
    if workflow_result.workflows_parsed > 0:
        typer.echo(f"  workflows parsed:    {workflow_result.workflows_parsed}")
    typer.echo(
        f"  detectors run:       {scan_result.detectors_run + workflow_result.detectors_run}"
    )
    typer.echo(f"  manifest files:      {manifest_result.files_found}")
    typer.echo(f"  manifests loaded:    {manifest_result.manifests_loaded}")
    typer.echo(f"  evidence records:    {total_evidence}")
    typer.echo(
        f"    from detectors:    {scan_result.evidence_count + workflow_result.evidence_count}"
    )
    typer.echo(f"    from manifests:    {manifest_result.evidence_count}")
    for det in scan_result.per_detector:
        typer.echo(f"    {det.detector_id}@{det.version:<7}  +{det.evidence_count}")
    for det in workflow_result.per_detector:
        typer.echo(f"    {det.detector_id}@{det.version:<7}  +{det.evidence_count}")
    for m in manifest_result.per_manifest:
        rel = m.file.relative_to(root) if m.file.is_absolute() else m.file
        typer.echo(f"    manifest {rel}  ksi={m.ksi}  +{m.attestation_count}")
    if manifest_result.skipped_unknown_ksi:
        # Primitive already deduplicates; join for display.
        skipped = ", ".join(manifest_result.skipped_unknown_ksi)
        typer.echo(f"  skipped manifest(s) for unknown KSI(s): {skipped}")

    # Priority 0 (2026-04-27): warn the user when an HCL-mode scan is hitting
    # a module-composed codebase. Detectors look at root-level resource blocks
    # only; resources defined inside upstream modules (the dominant ICP-A
    # pattern) are invisible without plan-JSON expansion. The 2026-04-27
    # dogfood pass against `aws-ia/terraform-aws-eks-blueprints/patterns/
    # blue-green-upgrade` is the worked example: 11 module calls, 9 resources,
    # 30 detectors, 1 firing. Plan-mode scans never trigger this warning
    # because module_calls defaults to 0 there (modules are already expanded).
    if plan_path is None and scan_result.should_recommend_plan_json:
        typer.echo("")
        typer.echo(
            f"  ⚠ {scan_result.module_calls} module calls detected; "
            f"detector coverage is limited in HCL mode."
        )
        typer.echo(
            "    Detectors look at root-level `resource` declarations only. Resources defined"
        )
        typer.echo("    inside upstream modules (the dominant ICP-A pattern) are invisible without")
        typer.echo("    plan-JSON expansion. For full coverage:")
        typer.echo("      terraform init")
        typer.echo("      terraform plan -out plan.bin")
        typer.echo("      terraform show -json plan.bin > plan.json")
        typer.echo("      efterlev scan --plan plan.json")

    if scan_result.parse_failures:
        # Surface unparseable files structurally so the user knows what was
        # skipped without grepping logs. Truncate the list at 10 to keep the
        # CLI output skimmable; the structured output (JSON, MCP) carries the
        # full list. python-hcl2 lags upstream Terraform syntax — for codebases
        # with persistent failures, plan-JSON mode (`--plan plan.json`) is the
        # workaround since plan-JSON is HashiCorp-emitted.
        typer.echo("")
        typer.echo(
            f"  ⚠ files skipped due to parse error: {scan_result.files_failed} "
            f"(scan continued with the {scan_result.resources_parsed} resources "
            f"that did parse)"
        )
        for fail in scan_result.parse_failures[:10]:
            typer.echo(f"    {fail.file}: {fail.reason}")
        if scan_result.files_failed > 10:
            typer.echo(f"    … and {scan_result.files_failed - 10} more")
        typer.echo("    For codebases with persistent failures, try plan-JSON mode:")
        typer.echo(
            "      terraform plan -out plan.bin && terraform show -json plan.bin > plan.json"
        )
        typer.echo("      efterlev scan --plan plan.json")

    # Hard-fail only if EVERY .tf file failed to parse — partial success is
    # the design (see ScanTerraformOutput.parse_failures). Zero resources +
    # zero failures = empty repo (legitimate; not a failure).
    if scan_result.parse_failures and scan_result.resources_parsed == 0:
        typer.echo("", err=True)
        typer.echo("error: every .tf file failed to parse; nothing to scan.", err=True)
        raise typer.Exit(code=1)
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
    sort: str = typer.Option(
        "severity",
        "--sort",
        help=(
            "How to order POA&M items. `severity` (default): not_implemented "
            "(HIGH) first, then partial (MEDIUM); alphabetical within tier. "
            "`csx-ord`: order by KSI-CSX-ORD's prescribed initial-authorization "
            "sequence (MAS, ADS, UCM, …); items outside the prescribed sequence "
            "appear after, alphabetically."
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
                "error: 0 Gap Agent classifications in the store. The Gap Agent "
                "either hasn't run yet, or ran with no evidence to classify "
                "(check `efterlev scan` first if you skipped that stage).",
                err=True,
            )
            raise typer.Exit(code=1)

        # Priority 4.2 (2026-04-27): build a {evidence_id -> boundary_state}
        # map from the store so we can drop POA&M items whose cited evidence
        # is entirely `out_of_boundary`. Out-of-scope findings are not in
        # the customer's FedRAMP boundary and don't belong in the POA&M.
        # `boundary_undeclared` and classifications with no cited evidence
        # (typical for `not_implemented` against a procedural KSI) flow
        # through — undeclared means "we don't know your scope" and an
        # uncited not_implemented is a real gap that needs tracking.
        evidence_boundary_state: dict[str, str] = {}
        for _rid, payload in store.iter_evidence():
            ev_id = payload.get("evidence_id")
            state = payload.get("boundary_state", "boundary_undeclared")
            if isinstance(ev_id, str):
                evidence_boundary_state[ev_id] = state

        kept_classifications = []
        skipped_out_of_boundary = 0
        for c in classifications:
            if not c.evidence_ids:
                # Uncited — keep. Real gap, not boundary-filterable.
                kept_classifications.append(c)
                continue
            states = [evidence_boundary_state.get(e, "boundary_undeclared") for e in c.evidence_ids]
            if all(s == "out_of_boundary" for s in states):
                skipped_out_of_boundary += 1
                continue
            kept_classifications.append(c)

        poam_inputs = [
            PoamClassificationInput(
                ksi_id=c.ksi_id,
                status=c.status,
                rationale=c.rationale,
                evidence_ids=list(c.evidence_ids),
                claim_record_id=None,  # the reconstructed shape doesn't carry record_id
            )
            for c in kept_classifications
        ]
        if sort not in ("severity", "csx-ord"):
            typer.echo(
                f"error: --sort must be 'severity' or 'csx-ord' (got '{sort}').",
                err=True,
            )
            raise typer.Exit(code=2)
        if sort == "csx-ord" and not frmr_doc.csx_ord_sequence:
            typer.echo(
                "warning: workspace's FRMR cache predates CSX-ORD support; "
                "the prescribed-sequence sort will fall back to alphabetical. "
                "Run `efterlev init --force` to refresh the cache.",
                err=True,
            )
        result = generate_poam_markdown(
            GeneratePoamMarkdownInput(
                classifications=poam_inputs,
                indicators=frmr_doc.indicators,
                baseline_id="fedramp-20x-moderate",
                frmr_version=frmr_doc.version,
                sort_mode=sort,  # type: ignore[arg-type]
                csx_ord_sequence=list(frmr_doc.csx_ord_sequence),
            )
        )

    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    output_path = output or (root / ".efterlev" / "reports" / f"poam-{timestamp}.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.markdown, encoding="utf-8")

    typer.echo(f"POA&M: {_display_path(output_path, target)}")
    typer.echo(f"  open items:       {result.item_count}")
    if skipped_out_of_boundary > 0:
        typer.echo(
            f"  out-of-boundary:  {skipped_out_of_boundary} item(s) excluded "
            "(their cited evidence is entirely out_of_boundary)"
        )
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

    count = write_redaction_log(ledger_obj, root / ".efterlev" / "redacted.log", scan_id=scan_id)
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
    from efterlev.config import load_config
    from efterlev.errors import AgentError, ConfigError
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

    try:
        config = load_config(root / ".efterlev" / "config.toml")
    except ConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    scan_id = _new_scan_id()
    ledger = RedactionLedger()

    try:
        with ProvenanceStore(root) as store:
            evidence = [Evidence.model_validate(p) for _rid, p in store.iter_evidence()]
            if not evidence:
                typer.echo(
                    "error: 0 evidence records in the store. The scan either hasn't run "
                    "yet or ran and matched no resources — your target may have no "
                    "Terraform/.github-workflows files in scope, or the 43 detectors "
                    "may not apply to its resources. Run `efterlev scan --target <path>` "
                    "to verify.",
                    err=True,
                )
                raise typer.Exit(code=1)

            # Priority 0 (2026-04-27): when the scan was HCL-mode against a
            # module-composed codebase, pass the summary so narratives reflect
            # the coverage limitation. None when no scan_terraform* primitive
            # invocation exists (already guarded by the `not evidence` check
            # above, but kept defensive).
            from efterlev.primitives.scan import latest_scan_summary

            scan_summary = latest_scan_summary(store)

            with active_store(store), active_redaction_ledger(ledger):
                agent = GapAgent(model=config.llm.model)
                with friendly_llm_error_handler():
                    report = agent.run(
                        GapAgentInput(
                            indicators=indicators,
                            evidence=evidence,
                            scan_summary=scan_summary,
                        )
                    )
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

    from efterlev.reports import render_gap_report_html, render_gap_report_json

    reports_dir = root / ".efterlev" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    generated_at = datetime.now().astimezone()

    html_body = render_gap_report_html(
        report,
        baseline_id="fedramp-20x-moderate",
        frmr_version=frmr_doc.version,
        evidence=evidence,
        generated_at=generated_at,
        themes=frmr_doc.themes,
        indicators=frmr_doc.indicators,
    )
    html_path = reports_dir / f"gap-{timestamp}.html"
    html_path.write_text(html_body, encoding="utf-8")

    json_data = render_gap_report_json(
        report,
        baseline_id="fedramp-20x-moderate",
        frmr_version=frmr_doc.version,
        evidence=evidence,
        generated_at=generated_at,
        themes=frmr_doc.themes,
        indicators=frmr_doc.indicators,
    )
    json_path = reports_dir / f"gap-{timestamp}.json"
    json_path.write_text(json.dumps(json_data, indent=2, sort_keys=True), encoding="utf-8")

    typer.echo("")
    typer.echo(f"HTML report: {_display_path(html_path, target)}")
    typer.echo(f"JSON sidecar: {_display_path(json_path, target)}")

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
    from efterlev.config import load_config
    from efterlev.errors import AgentError, ConfigError
    from efterlev.frmr.loader import FrmrDocument
    from efterlev.llm.scrubber import RedactionLedger, active_redaction_ledger
    from efterlev.models import Evidence
    from efterlev.primitives.generate import (
        GenerateFrmrAttestationInput,
        generate_frmr_attestation,
    )
    from efterlev.provenance import ProvenanceStore, active_store
    from efterlev.reports import (
        render_documentation_report_html,
        render_documentation_report_json,
    )

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
        config = load_config(root / ".efterlev" / "config.toml")
    except ConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

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
                    "error: 0 Gap Agent classifications in the store. The Gap Agent "
                    "either hasn't run yet, or ran with no evidence to classify "
                    "(check `efterlev scan` first if you skipped that stage).",
                    err=True,
                )
                raise typer.Exit(code=1)

            # Priority 0 (2026-04-27): scan_summary surfaces coverage
            # limitations to per-KSI narratives (HCL-mode against module
            # composition makes `not_implemented` ambiguous between "real
            # gap" and "scanner couldn't see it"). Same source as `agent gap`.
            from efterlev.primitives.scan import latest_scan_summary

            scan_summary = latest_scan_summary(store)

            from efterlev.cli.progress import TerminalProgressCallback

            agent = DocumentationAgent(model=config.llm.model)
            with friendly_llm_error_handler():
                report = agent.run(
                    DocumentationAgentInput(
                        indicators=frmr_doc.indicators,
                        evidence=evidence,
                        classifications=classifications,
                        baseline_id="fedramp-20x-moderate",
                        frmr_version=frmr_doc.version,
                        only_ksi=ksi,
                        scan_summary=scan_summary,
                    ),
                    progress_callback=TerminalProgressCallback(stage="documentation"),
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
                    machine_validation_cadence=config.cadence.machine_validation_cadence,
                    non_machine_validation_cadence=config.cadence.non_machine_validation_cadence,
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

    reports_dir = root / ".efterlev" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    generated_at = datetime.now().astimezone()

    html_body = render_documentation_report_html(
        report,
        baseline_id="fedramp-20x-moderate",
        frmr_version=frmr_doc.version,
        generated_at=generated_at,
    )
    html_path = reports_dir / f"documentation-{timestamp}.html"
    html_path.write_text(html_body, encoding="utf-8")

    json_data = render_documentation_report_json(
        report,
        baseline_id="fedramp-20x-moderate",
        frmr_version=frmr_doc.version,
        generated_at=generated_at,
    )
    json_path = reports_dir / f"documentation-{timestamp}.json"
    json_path.write_text(json.dumps(json_data, indent=2, sort_keys=True), encoding="utf-8")

    typer.echo("")
    typer.echo(f"HTML report: {_display_path(html_path, target)}")
    typer.echo(f"JSON sidecar: {_display_path(json_path, target)}")

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
    from efterlev.config import load_config
    from efterlev.errors import AgentError, ConfigError
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

    try:
        config = load_config(root / ".efterlev" / "config.toml")
    except ConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

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
                agent = RemediationAgent(model=config.llm.model)
                with friendly_llm_error_handler():
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

    from efterlev.reports import (
        render_remediation_proposal_html,
        render_remediation_proposal_json,
    )

    reports_dir = root / ".efterlev" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    generated_at = datetime.now().astimezone()

    html_body = render_remediation_proposal_html(
        proposal, evidence=ksi_evidence, generated_at=generated_at
    )
    # Include the KSI in the filename so running remediate for multiple KSIs
    # doesn't produce files that can only be distinguished by timestamp.
    html_path = reports_dir / f"remediation-{ksi}-{timestamp}.html"
    html_path.write_text(html_body, encoding="utf-8")

    json_data = render_remediation_proposal_json(proposal, generated_at=generated_at)
    json_path = reports_dir / f"remediation-{ksi}-{timestamp}.json"
    json_path.write_text(json.dumps(json_data, indent=2, sort_keys=True), encoding="utf-8")

    typer.echo("")
    typer.echo(f"HTML report: {_display_path(html_path, target)}")
    typer.echo(f"JSON sidecar: {_display_path(json_path, target)}")

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


@provenance_app.command("verify")
def provenance_verify(
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Repo containing the `.efterlev/` store. Defaults to the current directory.",
    ),
) -> None:
    """Detect tampering in the local provenance store.

    Backs the THREAT_MODEL.md T4 claim: "the provenance DB stores record
    hashes; `efterlev provenance verify` detects mismatches." The store
    is content-addressed (SHA-256 of canonical bytes), so any modification
    to a blob changes its hash and breaks the `(record_id → content_ref →
    file)` chain. This command walks every record, recomputes the
    blob's SHA-256, and compares it to the hash embedded in the
    sharded `content_ref` path (`xx/yy/xxyy<rest>.json`).

    Exit 0 = every blob matches its declared hash. Exit 1 = at least
    one mismatch (tampering, disk corruption, partial-write, etc.) or
    a missing blob. Output names each affected record explicitly.
    """
    import hashlib

    from efterlev.errors import ProvenanceError
    from efterlev.provenance import ProvenanceStore

    root = target.resolve()
    if not (root / ".efterlev").is_dir():
        typer.echo(
            f"error: no `.efterlev/` directory under {root}. Run `efterlev init` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    findings: list[str] = []
    record_count = 0
    try:
        with ProvenanceStore(root) as store:
            for record_id, content_ref in store.iter_record_refs():
                record_count += 1
                blob_path = store.blob_dir / content_ref
                if not blob_path.exists():
                    findings.append(f"  ✗ {record_id}: blob missing at {content_ref}")
                    continue
                actual = hashlib.sha256(blob_path.read_bytes()).hexdigest()
                # Sharded content_ref shape: 9a/20/9a205d96…json. Pull
                # the embedded hash out of the filename stem.
                expected = blob_path.stem
                if actual != expected:
                    findings.append(
                        f"  ✗ {record_id}: blob hash {actual[:12]}… does not match "
                        f"declared {expected[:12]}… (path: {content_ref})"
                    )
    except ProvenanceError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"verified {record_count} record(s)")
    if findings:
        typer.echo("")
        typer.echo("MISMATCHES (tamper-evidence):")
        for f in findings:
            typer.echo(f)
        typer.echo("")
        typer.echo(
            "  Each mismatch indicates either tampering, disk corruption, or a partial write."
        )
        raise typer.Exit(code=1)
    typer.echo("RESULT: clean. Every blob matches its content-addressed hash.")


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


@detectors_app.command("list")
def detectors_list() -> None:
    """List every detector registered with the runtime registry.

    Promised by THREAT_MODEL.md as the path to inspect what's loaded —
    "shows all loaded detectors, including third-party, before any scan
    runs." Useful as a defense-in-depth check (detect a registration
    regression like the 16-of-30 bug found 2026-04-25 dogfooding) and
    as introspection for users adding third-party detectors.

    Output is `<id>@<version>  <source>  ksis: ...  controls: ...`
    sorted by detector id. Stable output shape; safe to grep / pipe.
    """
    import efterlev.detectors  # noqa: F401  (registration side-effect)
    from efterlev.detectors.base import get_registry

    specs = sorted(get_registry().values(), key=lambda s: s.id)
    if not specs:
        typer.echo("(no detectors registered)")
        return
    for spec in specs:
        # Priority 6 (2026-04-27): visually distinguish KSI-mapped detectors
        # from supplementary 800-53-only ones. The latter still emit valid
        # evidence; they just don't contribute to KSI roll-ups because their
        # underlying controls (SC-28, IA-5, AC-3) are not in any FRMR
        # 0.9.43-beta KSI's `controls` array. Tracked upstream.
        if spec.ksis:
            tag = ""
            ksis = ", ".join(spec.ksis)
        else:
            tag = "  [800-53 only]"
            ksis = "—"
        controls = ", ".join(spec.controls) if spec.controls else "—"
        typer.echo(f"  {spec.id}@{spec.version}  source={spec.source}{tag}")
        typer.echo(f"      ksis:     {ksis}")
        typer.echo(f"      controls: {controls}")
    typer.echo("")
    ksi_mapped_count = sum(1 for s in specs if s.ksis)
    only_800_53_count = len(specs) - ksi_mapped_count
    typer.echo(
        f"  total: {len(specs)} detectors  "
        f"({ksi_mapped_count} KSI-mapped, {only_800_53_count} 800-53 only)"
    )


# --- boundary CLI (Priority 4.2, 2026-04-27) ------------------------------

# A FedRAMP customer typically has GovCloud Terraform in scope and commercial
# Terraform out of scope. These verbs let them declare scope and inspect it.
# `set` writes the workspace's `[boundary]` config; `show` reads it; `check`
# tests one path against the current rules. Acts on `.efterlev/config.toml`
# under `--target` (default: cwd), the same convention as every other
# workspace-touching command.


@boundary_app.command("set")
def boundary_set(
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the workspace whose `.efterlev/config.toml` will be modified.",
    ),
    include: list[str] = typer.Option(
        [],
        "--include",
        help=(
            "Glob pattern (gitignore-style) for paths IN the boundary. "
            "Pass multiple times for multiple patterns."
        ),
    ),
    exclude: list[str] = typer.Option(
        [],
        "--exclude",
        help=(
            "Glob pattern (gitignore-style) for paths OUT of the boundary. "
            "Pass multiple times. Exclude takes precedence over include."
        ),
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        help=(
            "Replace existing patterns instead of appending. By default, new "
            "patterns are added to whatever was already configured."
        ),
    ),
) -> None:
    """Declare which paths are inside the FedRAMP authorization boundary.

    Patterns are gitignore-style: `boundary/**` matches anything under
    `boundary/`, `**/main.tf` matches all `main.tf` anywhere. Exclude
    takes precedence over include — a path matching both is `out_of_boundary`.

    Without an explicit declaration, every Evidence is `boundary_undeclared`
    and the workspace cannot produce a defensible scope statement to a 3PAO.
    """
    from efterlev.config import BoundaryConfig, load_config, save_config
    from efterlev.errors import ConfigError

    if not include and not exclude:
        typer.echo(
            "error: pass at least one --include or --exclude pattern (use "
            "`efterlev boundary show` to view current rules).",
            err=True,
        )
        raise typer.Exit(code=2)

    root = target.resolve()
    config_path = root / ".efterlev" / "config.toml"
    try:
        config = load_config(config_path)
    except ConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    if replace:
        new_include = list(include)
        new_exclude = list(exclude)
    else:
        new_include = list(config.boundary.include) + list(include)
        new_exclude = list(config.boundary.exclude) + list(exclude)

    new_boundary = BoundaryConfig(include=new_include, exclude=new_exclude)
    new_config = config.model_copy(update={"boundary": new_boundary})
    save_config(new_config, config_path)

    typer.echo(f"Updated {config_path}")
    if new_include:
        typer.echo(f"  include ({len(new_include)}): {', '.join(new_include)}")
    if new_exclude:
        typer.echo(f"  exclude ({len(new_exclude)}): {', '.join(new_exclude)}")


@boundary_app.command("show")
def boundary_show(
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the workspace whose boundary will be displayed.",
    ),
) -> None:
    """Show the workspace's current boundary declaration.

    When no patterns are configured, the workspace is `boundary_undeclared`
    and Evidence flows through unfiltered — agents cannot tell a 3PAO which
    findings represent the in-scope boundary.
    """
    from efterlev.config import load_config
    from efterlev.errors import ConfigError

    root = target.resolve()
    try:
        config = load_config(root / ".efterlev" / "config.toml")
    except ConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    boundary = config.boundary
    if not boundary.include and not boundary.exclude:
        typer.echo("No boundary declared (status: boundary_undeclared).")
        typer.echo("")
        typer.echo("Run `efterlev boundary set --include 'boundary/**'` to declare scope.")
        return

    typer.echo("Boundary patterns (gitignore-style):")
    if boundary.include:
        typer.echo(f"  include ({len(boundary.include)}):")
        for p in boundary.include:
            typer.echo(f"    {p}")
    if boundary.exclude:
        typer.echo(f"  exclude ({len(boundary.exclude)}):")
        for p in boundary.exclude:
            typer.echo(f"    {p}")
    typer.echo("")
    typer.echo("Decision precedence: exclude wins over include.")


@boundary_app.command("check")
def boundary_check(
    path: str = typer.Argument(
        ...,
        help="Repo-relative path to test against the boundary patterns.",
    ),
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the workspace whose boundary patterns will be applied.",
    ),
) -> None:
    """Test whether a repo-relative path is in/out of the declared boundary.

    Useful when adjusting boundary patterns to verify the rules behave
    as expected before re-running a scan.
    """
    from efterlev.boundary import compute_boundary_state
    from efterlev.config import load_config
    from efterlev.errors import ConfigError

    root = target.resolve()
    try:
        config = load_config(root / ".efterlev" / "config.toml")
    except ConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    state = compute_boundary_state(path, config.boundary)
    typer.echo(f"{path}  →  {state}")


@app.command()
def doctor(
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the workspace whose .efterlev/ state will be inspected.",
    ),
) -> None:
    """Run pre-flight diagnostic checks.

    Verifies Python version, ANTHROPIC_API_KEY shape, .efterlev/
    initialization, FRMR cache freshness, and Bedrock credentials.
    Prints per-check pass/warn/fail with remediation hints. Exits
    non-zero only on `fail`-status checks (warnings are informational).

    No network calls — strictly local introspection.
    """
    from efterlev.cli.doctor import has_failures, run_doctor_checks

    root = target.resolve()
    checks = run_doctor_checks(root)

    badge = {"pass": "✓", "warn": "!", "fail": "✗"}
    typer.echo("Efterlev doctor — pre-flight checks")
    typer.echo("")
    for c in checks:
        line = f"  {badge[c.status]} {c.status:5}  {c.name:24}  {c.detail}"
        typer.echo(line)
        if c.hint:
            typer.echo(f"           hint: {c.hint}")
    typer.echo("")
    fail_count = sum(1 for c in checks if c.status == "fail")
    warn_count = sum(1 for c in checks if c.status == "warn")
    pass_count = sum(1 for c in checks if c.status == "pass")
    typer.echo(f"summary: {pass_count} pass, {warn_count} warn, {fail_count} fail")

    if has_failures(checks):
        raise typer.Exit(code=1)


@report_app.command("run")
def report_run(
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the repo to run the full pipeline against.",
    ),
    skip_init: bool = typer.Option(
        False,
        "--skip-init",
        help="Skip the init step. Useful when re-running on a workspace already initialized.",
    ),
    skip_document: bool = typer.Option(
        False,
        "--skip-document",
        help=(
            "Skip the Documentation Agent stage. Useful for fast iteration "
            "loops where you only care about gap classification."
        ),
    ),
    skip_poam: bool = typer.Option(
        False,
        "--skip-poam",
        help="Skip the POA&M generation stage.",
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        help=(
            "After the initial run, watch --target for changes to .tf, "
            ".tfvars, .yml, .yaml, .json files and re-run the pipeline "
            "(debounced 2s). Ctrl-C exits."
        ),
    ),
) -> None:
    """Run the full pipeline: init → scan → agent gap → agent document → poam.

    Each stage runs in sequence; if any stage exits non-zero, the
    pipeline stops and propagates the exit code. Per-stage flags
    (--skip-init, --skip-document, --skip-poam) let you tailor the
    pipeline to your situation. Add --watch to stay running and
    re-execute the pipeline on file changes (debounced 2s).
    """
    target_resolved = target.resolve()

    def run_once() -> None:
        target_str = str(target_resolved)

        # If `.efterlev/` already exists, skip init by default to avoid the
        # "directory exists" error that init raises without --force.
        efterlev_dir_exists = (target_resolved / ".efterlev").is_dir()
        skip_init_effective = skip_init or efterlev_dir_exists

        stages: list[tuple[str, list[str]]] = []
        if not skip_init_effective:
            stages.append(("init", ["init", "--target", target_str]))
        stages.append(("scan", ["scan", "--target", target_str]))
        stages.append(("agent gap", ["agent", "gap", "--target", target_str]))
        if not skip_document:
            stages.append(("agent document", ["agent", "document", "--target", target_str]))
        if not skip_poam:
            stages.append(("poam", ["poam", "--target", target_str]))

        typer.echo(f"Pipeline: {' → '.join(name for name, _ in stages)}")
        typer.echo("")

        for stage_idx, (name, args) in enumerate(stages, start=1):
            typer.echo("")
            typer.echo(f"━━━ [{stage_idx}/{len(stages)}] {name} ━━━")
            typer.echo("")
            try:
                # `standalone_mode=False` makes Click RETURN an int exit code
                # on `typer.Exit` (rather than raising). We must check the
                # return value as well as the exception path; otherwise a
                # stage that raises `typer.Exit(code=1)` slips through and
                # the orchestrator falsely declares success.
                rv = app(args, standalone_mode=False)
            except typer.Exit as e:
                # Defensive — older click versions (or non-standalone wrappers)
                # may still raise here.
                if e.exit_code and e.exit_code != 0:
                    typer.echo(
                        f"\nerror: pipeline stopped — `{name}` exited with code {e.exit_code}",
                        err=True,
                    )
                    raise
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
                if code != 0:
                    typer.echo(
                        f"\nerror: pipeline stopped — `{name}` raised SystemExit({code})",
                        err=True,
                    )
                    raise typer.Exit(code=code) from e
            else:
                # Returned-int-exit-code path. Click sets `rv` to the int
                # the stage raised via `typer.Exit(code=N)` when
                # standalone_mode=False; non-zero is failure.
                if isinstance(rv, int) and rv != 0:
                    typer.echo(
                        f"\nerror: pipeline stopped — `{name}` exited with code {rv}",
                        err=True,
                    )
                    raise typer.Exit(code=rv)

        typer.echo("")
        typer.echo("✓ Pipeline complete.")

    # First run: always.
    try:
        run_once()
    except typer.Exit:
        if not watch:
            raise
        # In watch mode, the initial pipeline failure shouldn't kill the
        # watcher — the user can fix the issue and re-trigger by saving.
        typer.echo("(initial run failed; continuing to watch — fix and save to retry)", err=True)

    if not watch:
        return

    # --watch: stay running, re-execute on file change.
    from efterlev.cli.watch import watch_loop

    typer.echo("")
    typer.echo(f"Watching {target_resolved} for changes (Ctrl-C to exit)...", err=True)

    def on_change() -> None:
        typer.echo("", err=True)
        typer.echo("━━━ change detected — re-running pipeline ━━━", err=True)
        typer.echo("")
        try:
            run_once()
        except typer.Exit as e:
            typer.echo(
                f"(re-run failed with exit {e.exit_code}; fix and save to retry)",
                err=True,
            )

    try:
        watch_loop(target_resolved, on_change=on_change)
    except KeyboardInterrupt:
        typer.echo("", err=True)
        typer.echo("Watch mode exited.", err=True)


@report_app.command("diff")
def report_diff(
    prior: Path = typer.Argument(
        ...,
        help="Path to a prior gap-report JSON sidecar (e.g. .efterlev/reports/gap-<ts>.json).",
    ),
    current: Path = typer.Argument(
        ...,
        help="Path to the current gap-report JSON sidecar.",
    ),
    target: Path = typer.Option(
        Path("."),
        "--target",
        help="Path to the workspace whose .efterlev/reports/ will receive the diff output.",
    ),
) -> None:
    """Compute and render a diff between two gap-report JSON sidecars.

    Emits both `gap-diff-<ts>.html` (reviewer-friendly) and
    `gap-diff-<ts>.json` (machine-readable, schema-versioned) under
    `.efterlev/reports/` of the target workspace. Exits non-zero if the
    diff contains any regressed KSIs — useful in CI for blocking PRs
    that regress posture.
    """
    from efterlev.reports import compute_gap_diff, render_gap_diff_html

    if not prior.is_file():
        typer.echo(f"error: prior file not found: {prior}", err=True)
        raise typer.Exit(code=1)
    if not current.is_file():
        typer.echo(f"error: current file not found: {current}", err=True)
        raise typer.Exit(code=1)

    try:
        prior_data = json.loads(prior.read_text(encoding="utf-8"))
        current_data = json.loads(current.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        typer.echo(f"error: invalid JSON: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        diff = compute_gap_diff(prior_data, current_data)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"Comparing {prior.name} → {current.name}")
    typer.echo(f"  added:      {len(diff.added)}")
    typer.echo(f"  removed:    {len(diff.removed)}")
    typer.echo(f"  improved:   {len(diff.improved)}")
    typer.echo(f"  regressed:  {len(diff.regressed)}")
    typer.echo(f"  unchanged:  {len(diff.unchanged)}")

    root = target.resolve()
    reports_dir = root / ".efterlev" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    generated_at = datetime.now().astimezone()

    html_body = render_gap_diff_html(diff, generated_at=generated_at)
    html_path = reports_dir / f"gap-diff-{timestamp}.html"
    html_path.write_text(html_body, encoding="utf-8")

    json_path = reports_dir / f"gap-diff-{timestamp}.json"
    json_path.write_text(json.dumps(diff.model_dump(), indent=2, sort_keys=True), encoding="utf-8")

    typer.echo("")
    typer.echo(f"HTML report: {_display_path(html_path, target)}")
    typer.echo(f"JSON sidecar: {_display_path(json_path, target)}")

    if diff.regressed:
        typer.echo("")
        typer.echo(
            f"warning: {len(diff.regressed)} KSI(s) regressed since the prior scan.",
            err=True,
        )
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
