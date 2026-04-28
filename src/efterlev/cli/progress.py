"""Per-unit progress callbacks for long-running agent stages.

Priority 3.5 (2026-04-28). Without this, the Documentation Agent runs
silently for ~7 minutes producing 60 KSI narratives and users think
the process hung. This module defines a small `ProgressCallback`
protocol, a no-op implementation for callers that don't want output,
and a `TerminalProgressCallback` for CLI use that emits one line per
completed unit.

Behavior:
  - TTY:     `[12/60] KSI-SVC-SNT ✓` printed with newline.
  - non-TTY: identical output (one line per unit).

We deliberately do NOT do `\\r`-overwrite or in-place-update tricks.
They look slick on a TTY but break log capture (logging tools see one
giant garbled line) and complicate the protocol. One-line-per-unit is
boring and correct.

Usage from an agent:

    callback = input.progress_callback or NoopProgressCallback()
    callback.on_unit_complete(ksi_id, idx, total, success=True)

Usage from the CLI:

    from efterlev.cli.progress import TerminalProgressCallback
    callback = TerminalProgressCallback(stage="agent document")
    agent.run(DocumentationAgentInput(..., progress_callback=callback))
"""

from __future__ import annotations

import sys
from typing import Protocol


class ProgressCallback(Protocol):
    """Hook for an agent to report per-unit progress.

    Agents that process N units (e.g. N KSIs, N detectors) call
    `on_unit_complete` after each unit finishes. The callback decides
    what to do — print, log, update a UI, etc.

    `success=True` means the unit produced output without error.
    `success=False` means the unit hit an exception (and the agent will
    propagate it upward — the callback gets a chance to log first).
    """

    def on_unit_complete(
        self,
        unit_id: str,
        idx: int,
        total: int,
        *,
        success: bool,
    ) -> None: ...


class NoopProgressCallback:
    """Default callback that drops every event.

    Used when an agent's caller doesn't want progress output (e.g.
    tests, MCP server, non-interactive scripts that capture stdout
    structurally). Cleaner than scattering `if callback: callback(...)`
    checks through agent code.
    """

    def on_unit_complete(
        self,
        unit_id: str,
        idx: int,
        total: int,
        *,
        success: bool,
    ) -> None:
        return


class TerminalProgressCallback:
    """Print `[idx/total] unit_id ✓` (or `✗`) one line per completed unit.

    Output goes to stderr so it doesn't interleave with the agent's
    final report on stdout (gap.py / document.py write their summary
    tables and HTML paths on stdout).
    """

    def __init__(self, stage: str = "") -> None:
        self.stage = stage

    def on_unit_complete(
        self,
        unit_id: str,
        idx: int,
        total: int,
        *,
        success: bool,
    ) -> None:
        marker = "✓" if success else "✗"
        prefix = f"  [{self.stage}] " if self.stage else "  "
        print(f"{prefix}[{idx}/{total}] {unit_id} {marker}", file=sys.stderr, flush=True)
