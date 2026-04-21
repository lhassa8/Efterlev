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
    assert scan_result["evidence_count"] == 1
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
