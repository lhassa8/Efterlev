"""HTML + JSON rendering for `DocumentationReport` artifacts.

Companion to `gap_report.py`. Where the Gap Report is a compact
classification table, the Documentation Report is prose-heavy: one
per-KSI card with the full narrative the agent drafted plus its
evidence citations.

`render_documentation_report_html` returns a complete HTML document;
`render_documentation_report_json` returns the same data as a
JSON-serializable dict. The CLI writes both side-by-side
(`documentation-<ts>.html` + `documentation-<ts>.json`) so downstream
tooling consumers can read narratives + citations without HTML scraping.

HTML layout:
  1. Header + baseline/FRMR metadata + attestation count.
  2. "DRAFT — requires human review" banner (narratives are Claims).
  3. One `.record.claim` card per KSI attestation:
     - KSI id + status pill
     - Narrative body, preserving paragraph breaks via `white-space: pre-wrap`
     - Citations listing (evidence_id, detector_id, source_file:lines)
     - Claim record id for provenance walk
  4. Skipped-KSIs section for `not_applicable` / unknown-KSI entries.

JSON schema (v1):
  {
    "schema_version": "1.0",
    "report_type": "documentation",
    "generated_at": "<iso-8601>",
    "baseline_id": "<str>",
    "frmr_version": "<str>",
    "attestations": [
      {
        "ksi_id": "<str>",
        "status": "<status> | null",
        "mode": "<scanner_only|agent_drafted>",
        "narrative": "<str> | null",
        "controls_evidenced": ["<id>", ...],
        "citations": [
          {
            "evidence_id": "<id>",
            "detector_id": "<id>",
            "source_file": "<path>",
            "source_lines": "<lines> | null"
          }
        ],
        "claim_record_id": "<id> | null"
      }
    ],
    "skipped_ksi_ids": ["<id>", ...]
  }
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import Environment, select_autoescape

from efterlev.agents import DocumentationReport
from efterlev.reports.html import DRAFT_BANNER_HTML, render_base_document

DOCUMENTATION_REPORT_JSON_SCHEMA_VERSION = "1.0"

_BODY_TEMPLATE = """
{{ draft_banner }}

<p class="meta">
  Baseline: <code>{{ baseline_id }}</code> ·
  FRMR: <code>{{ frmr_version }}</code> ·
  Attestations drafted: <strong>{{ attestations | length }}</strong>
  {% if skipped_ksi_ids %}·
  Skipped: <strong>{{ skipped_ksi_ids | length }}</strong>{% endif %}
</p>

<h2>Attestations</h2>
{% for att in attestations %}
{% set draft = att.draft %}
<div class="record claim">
  <h3>
    <span class="ksi-id">{{ draft.ksi_id }}</span>
    {% if draft.status %}
    <span class="status-pill status-{{ draft.status }}">
      {{ draft.status | replace('_', ' ') }}
    </span>
    {% endif %}
  </h3>

  {% if draft.narrative %}
  <div class="narrative">{{ draft.narrative }}</div>
  {% else %}
  <div class="narrative"><em>No narrative — scanner-only skeleton.</em></div>
  {% endif %}

  {% if draft.citations %}
  <div class="citations">
    <strong>Evidence citations ({{ draft.citations | length }}):</strong>
    <ul>
    {% for cite in draft.citations %}
      <li>
        <code class="fence-id">{{ cite.evidence_id }}</code>
        {% if cite.detector_id == "manifest" -%}
        <span class="source-badge source-manifest"
              title="Human-signed procedural attestation from .efterlev/manifests/"
              >attestation</span>
        {%- endif %}
        — <code>{{ cite.detector_id }}</code>
        at <code>{{ cite.source_file
          }}{% if cite.source_lines %}:{{ cite.source_lines }}{% endif %}</code>
      </li>
    {% endfor %}
    </ul>
  </div>
  {% else %}
  <div class="citations"><em>No evidence cited in the skeleton.</em></div>
  {% endif %}

  {% if att.claim_record_id %}
  <div class="evidence-links">
    Provenance record: <code class="record-id">{{ att.claim_record_id }}</code>
  </div>
  {% endif %}
</div>
{% endfor %}

{% if skipped_ksi_ids %}
<h2>Skipped KSIs</h2>
<p class="meta">
  These KSIs were not drafted — either classified as
  <code>not_applicable</code> or not present in the loaded baseline.
</p>
<ul>
{% for ksi_id in skipped_ksi_ids %}
  <li><span class="ksi-id">{{ ksi_id }}</span></li>
{% endfor %}
</ul>
{% endif %}
"""

# Extra CSS to wrap narrative prose with preserved paragraph breaks. Appended
# to the base stylesheet via a <style> block in the body — avoids forking the
# shared stylesheet for a report-local concern. The `.source-badge` styles
# now live in the shared stylesheet in `reports/html.py` since Gap and
# Remediation reports carry the badge too.
_NARRATIVE_CSS = """
<style>
  .narrative {
    white-space: pre-wrap;
    margin-top: 10px;
    margin-bottom: 12px;
    color: #1a1a1a;
    line-height: 1.55;
  }
  .citations { margin-top: 10px; font-size: 13px; color: #4a4a4a; }
  .citations ul { margin: 6px 0 0 0; padding-left: 20px; }
  .citations li { margin-bottom: 3px; }
</style>
"""


def render_documentation_report_html(
    report: DocumentationReport,
    *,
    baseline_id: str,
    frmr_version: str,
    generated_at: datetime | None = None,
) -> str:
    """Return a complete HTML document rendering of a DocumentationReport."""
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(_BODY_TEMPLATE)
    body = template.render(
        attestations=report.attestations,
        skipped_ksi_ids=report.skipped_ksi_ids,
        baseline_id=baseline_id,
        frmr_version=frmr_version,
        draft_banner=DRAFT_BANNER_HTML,
    )

    when = (generated_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    return render_base_document(
        title="Documentation Report",
        subtitle=(
            f"{len(report.attestations)} attestation(s) drafted, "
            f"{len(report.skipped_ksi_ids)} skipped"
        ),
        body_html=_NARRATIVE_CSS + body,
        generated_at=when,
    )


def render_documentation_report_json(
    report: DocumentationReport,
    *,
    baseline_id: str,
    frmr_version: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Return the documentation report as a JSON-serializable dict.

    Mirrors `render_documentation_report_html`'s data view. Citations
    are flattened into a list of dicts (evidence_id, detector_id,
    source_file, source_lines); each attestation pairs its draft with
    the claim_record_id assigned at persistence time.
    """
    when = (generated_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    return {
        "schema_version": DOCUMENTATION_REPORT_JSON_SCHEMA_VERSION,
        "report_type": "documentation",
        "generated_at": when,
        "baseline_id": baseline_id,
        "frmr_version": frmr_version,
        "attestations": [
            {
                "ksi_id": att.draft.ksi_id,
                "status": att.draft.status,
                "mode": att.draft.mode,
                "narrative": att.draft.narrative,
                "controls_evidenced": list(att.draft.controls_evidenced),
                "citations": [
                    {
                        "evidence_id": cite.evidence_id,
                        "detector_id": cite.detector_id,
                        "source_file": cite.source_file,
                        "source_lines": cite.source_lines,
                    }
                    for cite in att.draft.citations
                ],
                "claim_record_id": att.claim_record_id,
            }
            for att in report.attestations
        ],
        "skipped_ksi_ids": list(report.skipped_ksi_ids),
    }
