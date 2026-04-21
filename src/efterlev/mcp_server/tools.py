"""MCP tool handlers — CLI-equivalent operations over the provenance store.

Each tool takes `target` as an explicit path (DECISIONS design call #4:
stateless server), opens a fresh `ProvenanceStore`, writes an
`mcp_tool_call` record for audit, then dispatches the underlying
operation under `active_store(...)`. Handlers are synchronous — the MCP
SDK's async layer awaits them via a thin wrapper in `server.py`.

Why handlers are hand-registered rather than auto-generated from the
`@primitive` registry: the MCP-facing shape is the *CLI verb*, not the
raw primitive. Users want "run the scan on this repo" more than "here
is a list of Evidence records to feed the scan_terraform primitive."
Primitive-level exposure can land in v1 without breaking these tools.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from efterlev.errors import EfterlevError
from efterlev.provenance import ProvenanceStore, active_store


@dataclass(frozen=True)
class ToolDef:
    """MCP tool metadata + dispatcher.

    `handler` takes the validated arguments dict and returns a JSON-
    serializable dict; the server wrapper converts that to `TextContent`.
    `input_schema` is JSON Schema (draft 2020-12) — the same thing the
    MCP SDK's `Tool.inputSchema` expects.
    """

    name: str
    description: str
    input_schema: dict[str, Any]


def _target_schema(
    extra_props: dict[str, Any] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    """Standard input schema helper: `target` is always required."""
    properties: dict[str, Any] = {
        "target": {
            "type": "string",
            "description": (
                "Absolute path to the repo containing (or about to contain) `.efterlev/`."
            ),
        },
    }
    if extra_props:
        properties.update(extra_props)
    return {
        "type": "object",
        "properties": properties,
        "required": ["target", *(required or [])],
        "additionalProperties": False,
    }


TOOLS: dict[str, ToolDef] = {
    "efterlev_init": ToolDef(
        name="efterlev_init",
        description=(
            "Initialize an Efterlev workspace in the target repo. Creates `.efterlev/`, "
            "verifies the vendored FRMR + NIST SP 800-53 catalog hashes, and writes a "
            "load-receipt provenance record. Idempotent only with --force."
        ),
        input_schema=_target_schema(
            extra_props={
                "baseline": {
                    "type": "string",
                    "description": "Baseline id (v0 supports 'fedramp-20x-moderate').",
                    "default": "fedramp-20x-moderate",
                },
                "force": {
                    "type": "boolean",
                    "description": "Overwrite an existing `.efterlev/` directory.",
                    "default": False,
                },
            },
        ),
    ),
    "efterlev_scan": ToolDef(
        name="efterlev_scan",
        description=(
            "Run all applicable detectors over the target repo's Terraform sources. "
            "Writes one Evidence record per detector hit into the provenance store. "
            "Requires `efterlev_init` to have been run first."
        ),
        input_schema=_target_schema(),
    ),
    "efterlev_agent_gap": ToolDef(
        name="efterlev_agent_gap",
        description=(
            "Run the Gap Agent: classify every baseline KSI as implemented / partial / "
            "not_implemented / not_applicable, grounded in scanner evidence already "
            "in the store. Requires ANTHROPIC_API_KEY in the server's environment."
        ),
        input_schema=_target_schema(),
    ),
    "efterlev_agent_document": ToolDef(
        name="efterlev_agent_document",
        description=(
            "Run the Documentation Agent: draft an FRMR-compatible attestation narrative "
            "per classified KSI, grounded in the evidence the Gap Agent cited. If `ksi` "
            "is set, drafts only for that KSI. Requires ANTHROPIC_API_KEY server-side."
        ),
        input_schema=_target_schema(
            extra_props={
                "ksi": {
                    "type": "string",
                    "description": "Optional KSI id; if set, drafts only for this KSI.",
                },
            },
        ),
    ),
    "efterlev_agent_remediate": ToolDef(
        name="efterlev_agent_remediate",
        description=(
            "Run the Remediation Agent: propose a Terraform diff closing the gap for a "
            "single KSI, grounded in the evidence and the .tf source files. Empty diff "
            "means the gap is procedural/policy-only. Requires ANTHROPIC_API_KEY "
            "server-side. Efterlev never applies the diff."
        ),
        input_schema=_target_schema(
            extra_props={
                "ksi": {"type": "string", "description": "KSI id to remediate."},
            },
            required=["ksi"],
        ),
    ),
    "efterlev_provenance_show": ToolDef(
        name="efterlev_provenance_show",
        description=(
            "Walk the provenance chain from a record id back to its source lines. "
            "Returns a rendered text tree plus the structured chain for consumers "
            "that want to re-render."
        ),
        input_schema=_target_schema(
            extra_props={
                "record_id": {
                    "type": "string",
                    "description": "sha256:<hex> record id to start the walk from.",
                },
            },
            required=["record_id"],
        ),
    ),
    "efterlev_list_primitives": ToolDef(
        name="efterlev_list_primitives",
        description=(
            "List every registered `@primitive` callable with its capability, version, "
            "determinism, and input/output model names. Architectural introspection — "
            "a second MCP client can discover what Efterlev can do without reading source."
        ),
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
}


def _log_tool_call(
    store: ProvenanceStore, tool: str, arguments: dict[str, Any], client_id: str
) -> None:
    """Write one `mcp_tool_call` claim record before dispatching the work.

    Done at the top of every handler so even a crash in the underlying
    operation leaves an audit trail. client_id is the MCP `clientInfo.name`
    as captured at the request layer; defaults to "unknown" when the
    server hasn't been told.
    """
    store.write_record(
        payload={"tool": tool, "arguments": arguments, "client_id": client_id},
        record_type="claim",
        agent="mcp_server@0.1.0",
        metadata={"kind": "mcp_tool_call", "tool": tool, "client_id": client_id},
    )


def dispatch_tool(
    name: str, arguments: dict[str, Any], *, client_id: str = "unknown"
) -> dict[str, Any]:
    """Dispatch a tool call. Returns a JSON-serializable dict.

    Raises `EfterlevError` on known failure modes (missing .efterlev,
    malformed input, etc.) — the server wrapper formats those as
    `CallToolResult(isError=True)` for the client.
    """
    if name not in TOOLS:
        raise EfterlevError(f"unknown tool: {name!r}")

    if name == "efterlev_list_primitives":
        return _tool_list_primitives()

    # Every other tool takes a target path and operates on a
    # ProvenanceStore. We log the call into that store before dispatch
    # so even a mid-handler exception leaves an audit record.
    target_raw = arguments.get("target")
    if not isinstance(target_raw, str):
        raise EfterlevError(f"tool {name!r} requires a `target` argument (string path)")
    target = Path(target_raw).resolve()

    if name == "efterlev_init":
        return _tool_init(
            target=target,
            baseline=arguments.get("baseline", "fedramp-20x-moderate"),
            force=bool(arguments.get("force", False)),
            client_id=client_id,
            name=name,
            arguments=arguments,
        )

    # All remaining tools require an existing .efterlev/.
    if not (target / ".efterlev").is_dir():
        raise EfterlevError(f"no `.efterlev/` directory under {target}. Run `efterlev_init` first.")

    with ProvenanceStore(target) as store:
        _log_tool_call(store, name, arguments, client_id)
        with active_store(store):
            if name == "efterlev_scan":
                return _tool_scan(target)
            if name == "efterlev_agent_gap":
                return _tool_agent_gap(target)
            if name == "efterlev_agent_document":
                return _tool_agent_document(target, arguments.get("ksi"))
            if name == "efterlev_agent_remediate":
                ksi = arguments.get("ksi")
                if not isinstance(ksi, str) or not ksi:
                    raise EfterlevError("`ksi` is required for efterlev_agent_remediate")
                return _tool_agent_remediate(target, ksi)
            if name == "efterlev_provenance_show":
                record_id = arguments.get("record_id")
                if not isinstance(record_id, str) or not record_id:
                    raise EfterlevError("`record_id` is required for efterlev_provenance_show")
                return _tool_provenance_show(store, record_id)

    raise EfterlevError(f"tool {name!r} not dispatched (bug)")


def _tool_list_primitives() -> dict[str, Any]:
    # Import-time registrations populate the registry; a simple snapshot suffices.
    import efterlev.primitives.generate  # ensure registry populated
    import efterlev.primitives.scan  # ensure registry populated
    from efterlev.primitives.base import get_registry

    # Touch the imports so ruff doesn't strip them as unused;
    # the side effect we want is the module import itself.
    _ = (efterlev.primitives.generate, efterlev.primitives.scan)

    entries = []
    for name, spec in sorted(get_registry().items()):
        entries.append(
            {
                "name": name,
                "version": spec.version,
                "capability": spec.capability,
                "deterministic": spec.deterministic,
                "side_effects": spec.side_effects,
                "input_model": spec.input_model.__name__,
                "output_model": spec.output_model.__name__,
            }
        )
    return {"primitives": entries}


def _tool_init(
    *,
    target: Path,
    baseline: str,
    force: bool,
    client_id: str,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    from efterlev.workspace import init_workspace

    result = init_workspace(target, baseline, force=force)
    # Post-init: the store now exists; log the tool call after the fact so
    # init itself shows up alongside any subsequent tool calls. Init is a
    # once-ever operation so missing the pre-dispatch audit row here is ok.
    with ProvenanceStore(target) as store:
        _log_tool_call(store, name, arguments, client_id)
    return {
        "status": "initialized",
        "efterlev_dir": str(result.efterlev_dir),
        "baseline": result.baseline,
        "frmr_version": result.frmr_version,
        "frmr_last_updated": result.frmr_last_updated,
        "num_themes": result.num_themes,
        "num_indicators": result.num_indicators,
        "num_controls": result.num_controls,
        "num_enhancements": result.num_enhancements,
        "receipt_record_id": result.receipt_record_id,
    }


def _tool_scan(target: Path) -> dict[str, Any]:
    from efterlev.primitives.scan import ScanTerraformInput, scan_terraform

    result = scan_terraform(ScanTerraformInput(target_dir=target))
    return {
        "resources_parsed": result.resources_parsed,
        "detectors_run": result.detectors_run,
        "evidence_count": result.evidence_count,
        "evidence_record_ids": result.evidence_record_ids,
        "per_detector": [d.model_dump(mode="json") for d in result.per_detector],
    }


def _tool_agent_gap(target: Path) -> dict[str, Any]:
    from efterlev.agents import GapAgent, GapAgentInput
    from efterlev.frmr.loader import FrmrDocument
    from efterlev.models import Evidence
    from efterlev.provenance import get_active_store

    store = get_active_store()
    assert store is not None  # guaranteed by dispatch_tool's activate-then-call shape

    frmr_cache = target / ".efterlev" / "cache" / "frmr_document.json"
    if not frmr_cache.is_file():
        raise EfterlevError(f"FRMR cache missing at {frmr_cache}. Re-run efterlev_init.")
    frmr_doc = FrmrDocument.model_validate_json(frmr_cache.read_text(encoding="utf-8"))
    indicators = list(frmr_doc.indicators.values())

    evidence = [Evidence.model_validate(p) for _rid, p in store.iter_evidence()]
    if not evidence:
        raise EfterlevError("no evidence records. Run efterlev_scan first.")

    agent = GapAgent()
    report = agent.run(GapAgentInput(indicators=indicators, evidence=evidence))
    return report.model_dump(mode="json")


def _tool_agent_document(target: Path, ksi: str | None) -> dict[str, Any]:
    from efterlev.agents import (
        DocumentationAgent,
        DocumentationAgentInput,
        reconstruct_classifications_from_store,
    )
    from efterlev.frmr.loader import FrmrDocument
    from efterlev.models import Evidence
    from efterlev.provenance import get_active_store

    store = get_active_store()
    assert store is not None

    frmr_cache = target / ".efterlev" / "cache" / "frmr_document.json"
    if not frmr_cache.is_file():
        raise EfterlevError(f"FRMR cache missing at {frmr_cache}. Re-run efterlev_init.")
    frmr_doc = FrmrDocument.model_validate_json(frmr_cache.read_text(encoding="utf-8"))

    evidence = [Evidence.model_validate(p) for _rid, p in store.iter_evidence()]
    classification_rows = store.iter_claims_by_metadata_kind("ksi_classification")
    classifications = reconstruct_classifications_from_store(classification_rows)
    if not classifications:
        raise EfterlevError("no Gap Agent classifications. Run efterlev_agent_gap first.")

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
    return report.model_dump(mode="json")


def _tool_agent_remediate(target: Path, ksi: str) -> dict[str, Any]:
    from efterlev.agents import (
        RemediationAgent,
        RemediationAgentInput,
        reconstruct_classifications_from_store,
    )
    from efterlev.frmr.loader import FrmrDocument
    from efterlev.models import Evidence
    from efterlev.provenance import get_active_store

    store = get_active_store()
    assert store is not None

    frmr_cache = target / ".efterlev" / "cache" / "frmr_document.json"
    if not frmr_cache.is_file():
        raise EfterlevError(f"FRMR cache missing at {frmr_cache}. Re-run efterlev_init.")
    frmr_doc = FrmrDocument.model_validate_json(frmr_cache.read_text(encoding="utf-8"))
    indicator = frmr_doc.indicators.get(ksi)
    if indicator is None:
        raise EfterlevError(f"KSI {ksi!r} is not in the loaded baseline (FRMR {frmr_doc.version}).")

    classification_rows = store.iter_claims_by_metadata_kind("ksi_classification")
    classifications = reconstruct_classifications_from_store(classification_rows)
    clf = next((c for c in classifications if c.ksi_id == ksi), None)
    if clf is None:
        raise EfterlevError(f"no Gap Agent classification for {ksi}. Run efterlev_agent_gap first.")
    if clf.status in ("implemented", "not_applicable"):
        return {
            "status": "skipped",
            "reason": f"KSI {ksi} is classified as {clf.status}; no remediation needed.",
        }

    all_evidence = [Evidence.model_validate(p) for _rid, p in store.iter_evidence()]
    ksi_evidence = [ev for ev in all_evidence if ksi in ev.ksis_evidenced]

    source_files: dict[str, str] = {}
    for ev in ksi_evidence:
        file_path = Path(str(ev.source_ref.file))
        full = file_path if file_path.is_absolute() else target / file_path
        key = str(ev.source_ref.file)
        if full.is_file() and key not in source_files:
            source_files[key] = full.read_text(encoding="utf-8")

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
    return proposal.model_dump(mode="json")


def _tool_provenance_show(store: ProvenanceStore, record_id: str) -> dict[str, Any]:
    from efterlev.provenance import render_chain_text, walk_chain

    tree = walk_chain(store, record_id)
    return {
        "record_id": record_id,
        "rendered": render_chain_text(tree),
        "chain": _chain_to_dict(tree),
    }


def _chain_to_dict(node: Any) -> dict[str, Any]:
    """Convert a ChainNode tree to nested dicts for JSON output."""
    return {
        "record_id": node.record.record_id,
        "record_type": node.record.record_type,
        "primitive": node.record.primitive,
        "agent": node.record.agent,
        "metadata": node.record.metadata,
        "timestamp": node.record.timestamp.isoformat(),
        "parents": [_chain_to_dict(p) for p in node.parents],
    }


def tool_definitions_as_json_string() -> str:
    """Convenience for tests: serialize every tool's metadata."""
    return json.dumps({n: t.__dict__ for n, t in TOOLS.items()}, indent=2, default=str)
