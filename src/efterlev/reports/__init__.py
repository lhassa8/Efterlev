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

from efterlev.reports.documentation_report import (
    DOCUMENTATION_REPORT_JSON_SCHEMA_VERSION,
    render_documentation_report_html,
    render_documentation_report_json,
)
from efterlev.reports.gap_report import (
    GAP_REPORT_JSON_SCHEMA_VERSION,
    render_gap_report_html,
    render_gap_report_json,
)
from efterlev.reports.html import DRAFT_BANNER_HTML, RECORDS_STYLESHEET, render_base_document
from efterlev.reports.remediation_report import (
    REMEDIATION_REPORT_JSON_SCHEMA_VERSION,
    render_remediation_proposal_html,
    render_remediation_proposal_json,
)

__all__ = [
    "DOCUMENTATION_REPORT_JSON_SCHEMA_VERSION",
    "DRAFT_BANNER_HTML",
    "GAP_REPORT_JSON_SCHEMA_VERSION",
    "RECORDS_STYLESHEET",
    "REMEDIATION_REPORT_JSON_SCHEMA_VERSION",
    "render_base_document",
    "render_documentation_report_html",
    "render_documentation_report_json",
    "render_gap_report_html",
    "render_gap_report_json",
    "render_remediation_proposal_html",
    "render_remediation_proposal_json",
]
