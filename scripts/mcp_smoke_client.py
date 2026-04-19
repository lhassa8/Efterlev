"""In-process MCP client that exercises `mcp_smoke_server.py`.

Spawns the smoke server as a subprocess over stdio, initializes a session, lists
its tools, invokes each one with known arguments, and prints the result. Used as
a regression check on the local MCP transport before the live Claude Code test.

Run: `uv run python scripts/mcp_smoke_client.py`
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_PATH = Path(__file__).resolve().parent / "mcp_smoke_server.py"


def unwrap_text(result: object) -> str:
    """Pull the text out of a CallToolResult; fall back to repr."""
    content = getattr(result, "content", None)
    if not content:
        return repr(result)
    first = content[0]
    return getattr(first, "text", None) or repr(first)


async def main() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        init = await session.initialize()
        print(f"server name:     {init.serverInfo.name}")
        print(f"server version:  {init.serverInfo.version}")
        print(f"protocol:        {init.protocolVersion}")

        tools = await session.list_tools()
        print(f"tools exposed:   {[t.name for t in tools.tools]}")
        for tool in tools.tools:
            desc = (tool.description or "").splitlines()[0]
            print(f"  - {tool.name}: {desc}")

        echo_result = await session.call_tool("echo", {"message": "smoke ok"})
        print(f"echo('smoke ok')         -> {unwrap_text(echo_result)}")

        add_result = await session.call_tool("add_two_numbers", {"a": 2, "b": 3})
        print(f"add_two_numbers(2, 3)    -> {unwrap_text(add_result)}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
