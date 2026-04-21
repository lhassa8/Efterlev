"""stdio MCP server wiring.

Thin async shim that declares the tools (metadata sourced from
`tools.TOOLS`) and dispatches invocations into synchronous handlers
(which is where the real work happens). No business logic lives here —
this file is the protocol adapter.

Per DECISIONS 2026-04-21 design call #4, we are stdio-only by design.
There's no TCP listener, no session auth, no per-tool ACL. The trust
boundary is the OS-level stdio pipe: whoever spawned this subprocess is
authorized to call every tool.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from efterlev import __version__
from efterlev.errors import EfterlevError
from efterlev.mcp_server.tools import TOOLS, dispatch_tool

log = logging.getLogger(__name__)


def build_server() -> Server[None, Any]:
    """Construct the MCP Server with every tool registered. Used by tests too."""
    server: Server[None, Any] = Server("efterlev", version=__version__)

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return [
            Tool(name=t.name, description=t.description, inputSchema=t.input_schema)
            for t in TOOLS.values()
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        # MCP's `request_context` carries client info; best-effort pull of the
        # name for the audit log. Falls back to "unknown" if the server is
        # called outside a request context (e.g., our in-process tests).
        client_id = "unknown"
        try:
            ctx = server.request_context
            client_info = getattr(ctx.session, "client_params", None)
            if client_info is not None:
                info = getattr(client_info, "clientInfo", None)
                if info is not None:
                    client_id = getattr(info, "name", "unknown") or "unknown"
        except LookupError:
            # No active request context — we're being called outside the
            # stdio server loop (e.g., tests). That's fine; just log as unknown.
            client_id = "unknown"

        try:
            result = dispatch_tool(name, arguments, client_id=client_id)
        except EfterlevError as e:
            # Return the error as a structured TextContent payload rather
            # than raising — MCP clients get a clean error string, and our
            # own typed exceptions don't leak as framework tracebacks.
            payload = {"error": str(e), "error_type": type(e).__name__}
            return [TextContent(type="text", text=json.dumps(payload, indent=2))]

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    return server


async def run_stdio_server() -> None:
    """Main entry point — reads JSON-RPC messages over stdin/stdout forever."""
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
