"""MCP server tests — exercise tool dispatch in-process, no stdio loop.

The stdio transport isn't unit-tested here (that would require a
subprocess harness). What we test:
  - `TOOLS` registry has every v0 tool with a valid JSON Schema.
  - `dispatch_tool` refuses unknown names and missing required args.
  - `efterlev_list_primitives` reflects the actual `@primitive` registry.
  - `efterlev_init` + `efterlev_scan` chain produces evidence through
    the MCP layer the same way the CLI does.
  - Each tool call writes an `mcp_tool_call` audit record into the
    target repo's provenance store before the work runs.
  - Agent tools surface a clean error (not a stacktrace) when their
    upstream state is missing (`no evidence`, `no classifications`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from efterlev.errors import EfterlevError
from efterlev.mcp_server import TOOLS, dispatch_tool
from efterlev.provenance import ProvenanceStore


def _write_encrypted_bucket(dir_: Path) -> None:
    (dir_ / "main.tf").write_text(
        'resource "aws_s3_bucket" "audit" {\n'
        '  bucket = "audit-logs"\n'
        "  server_side_encryption_configuration {\n"
        "    rule {\n"
        "      apply_server_side_encryption_by_default {\n"
        '        sse_algorithm = "AES256"\n'
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )


# -- registry shape ---------------------------------------------------------


def test_every_v0_tool_is_registered() -> None:
    expected = {
        "efterlev_init",
        "efterlev_scan",
        "efterlev_agent_gap",
        "efterlev_agent_document",
        "efterlev_agent_remediate",
        "efterlev_provenance_show",
        "efterlev_list_primitives",
    }
    assert expected <= set(TOOLS)


def test_each_tool_has_valid_input_schema() -> None:
    for name, tool in TOOLS.items():
        assert tool.name == name
        assert tool.description
        schema = tool.input_schema
        assert schema.get("type") == "object", f"{name} schema not object-typed"
        assert "properties" in schema, f"{name} schema missing properties"


def test_list_primitives_reflects_registry() -> None:
    result = dispatch_tool("efterlev_list_primitives", {})
    names = {p["name"] for p in result["primitives"]}
    # At least the two landed primitives should be present.
    assert "scan_terraform" in names
    assert "generate_frmr_skeleton" in names
    # Each entry carries the full metadata shape.
    for entry in result["primitives"]:
        assert set(entry) >= {
            "name",
            "version",
            "capability",
            "deterministic",
            "side_effects",
            "input_model",
            "output_model",
        }


# -- error paths ------------------------------------------------------------


def test_dispatch_rejects_unknown_tool() -> None:
    with pytest.raises(EfterlevError, match="unknown tool"):
        dispatch_tool("not_a_real_tool", {})


def test_server_call_tool_catches_unexpected_exception(tmp_path: Path) -> None:
    """A bug inside a handler should not leak a framework traceback to the client.

    The server's `call_tool` handler catches every exception (not just
    EfterlevError) and returns a generic `{"error": "internal error",
    "error_type": "<ClassName>"}` payload. This test patches
    `dispatch_tool` to raise something unexpected and asserts the wrapper
    is the one catching it.
    """
    import asyncio
    import json

    from efterlev.mcp_server import server as server_module

    built = server_module.build_server()
    # Find the registered call_tool handler — the MCP SDK stores handlers
    # indexed by request type, keyed on the Pydantic model class.
    from mcp.types import CallToolRequest

    handler = built.request_handlers[CallToolRequest]

    # Monkeypatch dispatch_tool to raise a non-EfterlevError exception.
    original = server_module.dispatch_tool

    def _boom(name: str, arguments: dict, *, client_id: str = "unknown") -> dict:
        raise TypeError("simulated handler bug")

    server_module.dispatch_tool = _boom
    try:
        # Simulate a CallToolRequest envelope.
        from mcp.types import CallToolRequestParams

        req = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(name="efterlev_list_primitives", arguments={}),
        )
        result = asyncio.run(handler(req))
    finally:
        server_module.dispatch_tool = original

    # The handler returns a CallToolResult with our structured error payload
    # as its only TextContent block. We deliberately do NOT raise (which
    # would make MCP set isError=True but would also leak the raw exception
    # text to the client); the JSON payload inside content carries the
    # error information in a form clients can parse.
    inner = result.root
    content = inner.content[0]
    payload = json.loads(content.text)
    assert payload["error"] == "internal error"
    assert payload["error_type"] == "TypeError"
    # Simulated message MUST NOT appear in the response — that's the whole
    # point of not leaking internal exception text to MCP clients.
    assert "simulated handler bug" not in content.text


def test_dispatch_rejects_missing_target(tmp_path: Path) -> None:
    with pytest.raises(EfterlevError, match="requires a `target`"):
        dispatch_tool("efterlev_scan", {})


def test_dispatch_rejects_scan_without_init(tmp_path: Path) -> None:
    with pytest.raises(EfterlevError, match=r"no `\.efterlev/` directory"):
        dispatch_tool("efterlev_scan", {"target": str(tmp_path)})


def test_dispatch_remediate_requires_ksi(tmp_path: Path) -> None:
    # init first so we get past the `.efterlev/` check and reach the ksi check.
    dispatch_tool(
        "efterlev_init",
        {"target": str(tmp_path), "baseline": "fedramp-20x-moderate"},
    )
    with pytest.raises(EfterlevError, match="`ksi` is required"):
        dispatch_tool("efterlev_agent_remediate", {"target": str(tmp_path)})


def test_dispatch_agent_gap_clean_error_when_no_evidence(tmp_path: Path) -> None:
    dispatch_tool("efterlev_init", {"target": str(tmp_path)})
    with pytest.raises(EfterlevError, match="no evidence records"):
        dispatch_tool("efterlev_agent_gap", {"target": str(tmp_path)})


# -- happy path through init + scan -----------------------------------------


def test_init_then_scan_produces_evidence_via_mcp_layer(tmp_path: Path) -> None:
    _write_encrypted_bucket(tmp_path)

    init_result = dispatch_tool("efterlev_init", {"target": str(tmp_path)})
    assert init_result["status"] == "initialized"
    assert init_result["num_indicators"] > 0
    assert init_result["baseline"] == "fedramp-20x-moderate"

    scan_result = dispatch_tool("efterlev_scan", {"target": str(tmp_path)})
    assert scan_result["resources_parsed"] == 1
    # 1 from aws.encryption_s3_at_rest (the bucket has SSE) + 1 from
    # aws.terraform_inventory (Priority 1.4, 2026-04-27 — workspace summary).
    assert scan_result["evidence_count"] == 2
    assert scan_result["detectors_run"] >= 1
    assert scan_result["evidence_record_ids"]


def test_tool_call_writes_mcp_tool_call_audit_record(tmp_path: Path) -> None:
    _write_encrypted_bucket(tmp_path)
    dispatch_tool("efterlev_init", {"target": str(tmp_path)}, client_id="test-harness")
    dispatch_tool("efterlev_scan", {"target": str(tmp_path)}, client_id="test-harness")

    with ProvenanceStore(tmp_path) as store:
        rows = store.iter_claims_by_metadata_kind("mcp_tool_call")

    # Exactly two MCP tool calls so far (init's post-dispatch log + scan's pre-dispatch log).
    assert len(rows) == 2
    tools_called = {meta["tool"] for _rid, meta, _payload in rows}
    assert tools_called == {"efterlev_init", "efterlev_scan"}
    # The client_id we passed into dispatch_tool flows through to the metadata.
    client_ids = {meta["client_id"] for _rid, meta, _payload in rows}
    assert client_ids == {"test-harness"}


def test_provenance_show_walks_chain_over_mcp(tmp_path: Path) -> None:
    _write_encrypted_bucket(tmp_path)
    dispatch_tool("efterlev_init", {"target": str(tmp_path)})
    scan_result = dispatch_tool("efterlev_scan", {"target": str(tmp_path)})

    rid = scan_result["evidence_record_ids"][0]
    walked = dispatch_tool(
        "efterlev_provenance_show",
        {"target": str(tmp_path), "record_id": rid},
    )
    assert walked["record_id"] == rid
    assert walked["rendered"]
    assert walked["chain"]["record_id"] == rid


def test_init_idempotent_only_with_force(tmp_path: Path) -> None:
    dispatch_tool("efterlev_init", {"target": str(tmp_path)})
    with pytest.raises(EfterlevError, match="already exists"):
        dispatch_tool("efterlev_init", {"target": str(tmp_path)})
    # With force, a re-init succeeds.
    result = dispatch_tool("efterlev_init", {"target": str(tmp_path), "force": True})
    assert result["status"] == "initialized"


# -- efterlev_doctor tool (Priority 3.1, 2026-04-28) ------------------------


def test_doctor_tool_registered() -> None:
    assert "efterlev_doctor" in TOOLS
    schema = TOOLS["efterlev_doctor"].input_schema
    assert "target" in schema["properties"]


def test_doctor_returns_check_results(tmp_path: Path) -> None:
    """Dispatching efterlev_doctor against a fresh dir returns warnings
    (no .efterlev/, no FRMR cache, etc.) but exits cleanly."""
    result = dispatch_tool("efterlev_doctor", {"target": str(tmp_path)})
    assert "checks" in result
    assert "summary" in result
    assert "has_failures" in result
    # Five canonical checks.
    names = [c["name"] for c in result["checks"]]
    assert names == [
        "python_version",
        "efterlev_dir",
        "frmr_cache",
        "anthropic_api_key",
        "bedrock_credentials",
    ]


def test_doctor_after_init_passes_efterlev_dir_check(tmp_path: Path) -> None:
    """Once `efterlev_init` has run, the efterlev_dir + frmr_cache checks
    pass. Other checks may still warn (no API key); has_failures stays
    False as long as no `fail` status appears."""
    dispatch_tool("efterlev_init", {"target": str(tmp_path)})
    result = dispatch_tool("efterlev_doctor", {"target": str(tmp_path)})
    by_name = {c["name"]: c for c in result["checks"]}
    assert by_name["efterlev_dir"]["status"] == "pass"
    assert by_name["frmr_cache"]["status"] == "pass"
    assert result["has_failures"] is False


# -- efterlev_report_diff tool (Priority 2.10, 2026-04-28) ------------------


def test_report_diff_tool_registered() -> None:
    assert "efterlev_report_diff" in TOOLS
    schema = TOOLS["efterlev_report_diff"].input_schema
    assert "prior_path" in schema["properties"]
    assert "current_path" in schema["properties"]


def test_report_diff_computes_diff_between_two_sidecars(tmp_path: Path) -> None:
    """Round-trip: write two on-disk gap-report sidecars, dispatch the
    tool, verify the diff outcome."""
    import json as _json

    prior_data = {
        "schema_version": "1.0",
        "report_type": "gap",
        "ksi_classifications": [{"ksi_id": "KSI-SVC-SNT", "status": "implemented"}],
    }
    current_data = {
        "schema_version": "1.0",
        "report_type": "gap",
        "ksi_classifications": [
            {"ksi_id": "KSI-SVC-SNT", "status": "partial"},  # regressed
            {"ksi_id": "KSI-IAM-MFA", "status": "implemented"},  # added
        ],
    }
    prior_p = tmp_path / "prior.json"
    current_p = tmp_path / "current.json"
    prior_p.write_text(_json.dumps(prior_data))
    current_p.write_text(_json.dumps(current_data))

    result = dispatch_tool(
        "efterlev_report_diff",
        {"prior_path": str(prior_p), "current_path": str(current_p)},
    )
    # The diff serializes via Pydantic model_dump — we get the same shape
    # the GapDiff JSON sidecar emits.
    assert "entries" in result
    by_id = {e["ksi_id"]: e for e in result["entries"]}
    assert by_id["KSI-SVC-SNT"]["outcome"] == "status_changed"
    assert by_id["KSI-SVC-SNT"]["severity_movement"] == "regressed"
    assert by_id["KSI-IAM-MFA"]["outcome"] == "added"


def test_report_diff_rejects_missing_prior(tmp_path: Path) -> None:
    """Missing prior file → clean EfterlevError (not a raw OSError)."""
    current_p = tmp_path / "current.json"
    current_p.write_text("{}")
    with pytest.raises(EfterlevError, match="prior_path file not found"):
        dispatch_tool(
            "efterlev_report_diff",
            {"prior_path": str(tmp_path / "missing.json"), "current_path": str(current_p)},
        )


def test_report_diff_rejects_invalid_json(tmp_path: Path) -> None:
    prior_p = tmp_path / "prior.json"
    current_p = tmp_path / "current.json"
    prior_p.write_text("not valid json {")
    current_p.write_text("{}")
    with pytest.raises(EfterlevError, match="invalid JSON"):
        dispatch_tool(
            "efterlev_report_diff",
            {"prior_path": str(prior_p), "current_path": str(current_p)},
        )


def test_report_diff_rejects_wrong_report_type(tmp_path: Path) -> None:
    """Sidecar with `report_type=documentation` is rejected (the diff is
    gap-report-shaped only)."""
    import json as _json

    prior_p = tmp_path / "prior.json"
    current_p = tmp_path / "current.json"
    prior_p.write_text(_json.dumps({"report_type": "documentation", "ksi_classifications": []}))
    current_p.write_text(_json.dumps({"report_type": "gap", "ksi_classifications": []}))
    with pytest.raises(EfterlevError, match="expected 'gap'"):
        dispatch_tool(
            "efterlev_report_diff",
            {"prior_path": str(prior_p), "current_path": str(current_p)},
        )


def test_report_diff_rejects_missing_path_argument(tmp_path: Path) -> None:
    """Missing required argument surfaces as a clean error."""
    with pytest.raises(EfterlevError, match="prior_path` and `current_path"):
        dispatch_tool("efterlev_report_diff", {"prior_path": str(tmp_path / "x.json")})
