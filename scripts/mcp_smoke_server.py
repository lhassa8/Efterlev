"""Minimal stdio MCP server for pre-hackathon transport verification.

Exposes two trivial tools over stdio:
    - `echo(message: str) -> str`
    - `add_two_numbers(a: float, b: float) -> float`

This is not a stand-in for the real `src/efterlev/mcp_server/`; it exists only to
prove the FastMCP + stdio plumbing works on this Python 3.12 install and that an
external Claude Code session can discover and invoke an Efterlev-hosted tool.
Delete or replace once the real primitive registration lands during the hackathon.

Run directly:   `uv run python scripts/mcp_smoke_server.py`
Exercise via:   `uv run python scripts/mcp_smoke_client.py`
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("efterlev-smoke")


@mcp.tool()
def echo(message: str) -> str:
    """Return the message verbatim. Pre-hackathon MCP smoke test."""
    return message


@mcp.tool()
def add_two_numbers(a: float, b: float) -> float:
    """Return the sum of two numbers. Pre-hackathon MCP smoke test."""
    return a + b


if __name__ == "__main__":
    mcp.run()
