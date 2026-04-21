"""MCP server — exposes Efterlev's CLI verbs as MCP tools over stdio.

Per DECISIONS 2026-04-21 design call #4: stdio-only, stateless, logged.
Every tool call writes an `mcp_tool_call` claim record into the target
repo's provenance store before dispatching the underlying work, so
external callers are auditable the same way local CLI runs are.

Public entry point is `run_stdio_server()`, invoked by the
`efterlev mcp serve` CLI command. The tool handlers themselves are
plain Python functions exposed in `tools`, testable in-process without
the stdio loop.
"""

from __future__ import annotations

from efterlev.mcp_server.server import build_server, run_stdio_server
from efterlev.mcp_server.tools import TOOLS, ToolDef, dispatch_tool

__all__ = [
    "TOOLS",
    "ToolDef",
    "build_server",
    "dispatch_tool",
    "run_stdio_server",
]
