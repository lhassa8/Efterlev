"""HTML report rendering for Efterlev's agent outputs.

Per CLAUDE.md's "Evidence vs. claims" discipline, every rendered report
visually distinguishes Evidence (deterministic, high-trust, green
border) from Claims (LLM-reasoned, requires review, amber border + DRAFT
banner). That distinction is the single most important thing the output
layer preserves.

The renderers produce self-contained HTML strings — no external CSS, no
JavaScript — so a user can email / attach / archive a report without
worrying about broken links. Jinja2 handles templating; the base
template in `html.py` provides the shared shell (head, CSS, banner),
and per-artifact renderers in sibling modules produce the body content.

Written to disk under `.efterlev/reports/<kind>-<timestamp>.html` by
the CLI. Keeping the renderers pure-function (typed-input → string-out)
keeps them testable in isolation and reusable from the MCP server layer
without additional plumbing.
"""

from __future__ import annotations

from efterlev.reports.gap_report import render_gap_report_html
from efterlev.reports.html import DRAFT_BANNER_HTML, RECORDS_STYLESHEET, render_base_document

__all__ = [
    "DRAFT_BANNER_HTML",
    "RECORDS_STYLESHEET",
    "render_base_document",
    "render_gap_report_html",
]
