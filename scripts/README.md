# scripts/

Developer-facing helper scripts. Not part of the shipped `efterlev` package and
not imported by the library code. Each script is intended to be runnable
standalone via `uv run python scripts/<name>.py`.

## Contents

- `trestle_smoke.py` — loads the vendored NIST SP 800-53 Rev 5 catalog via
  `compliance-trestle` and prints metadata plus a recursive control count.
  Used once pre-hackathon to confirm the Python 3.12 install is clean.
- `mcp_smoke_server.py` — minimal stdio MCP server exposing two trivial
  tools (`echo`, `add_two_numbers`) via FastMCP. Used pre-hackathon to
  verify the transport works on this install and, paired with a live
  Claude Code session, to prove the architectural "external agent
  discovers an Efterlev primitive" moment end-to-end.
- `mcp_smoke_client.py` — in-process MCP client that spawns the smoke
  server as a subprocess, initializes a session, lists its tools, and
  calls each one. Regression harness for the transport.

These scripts are expected to be replaced or removed as the real library
and `src/efterlev/mcp_server/` wiring lands during the hackathon.

## Live Claude Code verification (manual)

The programmatic round-trip via `mcp_smoke_client.py` confirms the stdio
plumbing works. The architectural proof also requires a second, external
Claude Code session to discover and call the smoke server — this is the
moment the v0 demo depends on.

To wire it up locally:

```bash
# From the repo root, once:
claude mcp add efterlev-smoke -- \
  uv --project "$PWD" run python scripts/mcp_smoke_server.py
```

Then in a fresh Claude Code session in any directory, ask it to list
MCP tools or to call `mcp__efterlev-smoke__echo` with a message. A
successful response (the echoed message, the computed sum) is the
pre-hackathon green check for item 7.

If `claude mcp add` is unavailable in your environment, you can instead
add the server to `~/.claude.json` under the `mcpServers` key:

```json
{
  "mcpServers": {
    "efterlev-smoke": {
      "command": "uv",
      "args": ["--project", "/absolute/path/to/Efterlev",
               "run", "python", "scripts/mcp_smoke_server.py"]
    }
  }
}
```

Remove the entry after verification — this is a smoke test, not a
long-lived MCP server.
