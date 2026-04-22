"""HTML rendering for `DocumentationReport` artifacts.

Companion to `gap_report.py`. Where the Gap Report is a compact
classification table, the Documentation Report is prose-heavy: one
per-KSI card with the full narrative the agent drafted plus its
evidence citations.

Layout:
  1. Header + baseline/FRMR metadata + attestation count.
  2. "DRAFT — requires human review" banner (narratives are Claims).
  3. One `.record.claim` card per KSI attestation:
     - KSI id + status pill
     - Narrative body, preserving paragraph breaks via `white-space: pre-wrap`
     - Citations listing (evidence_id, detector_id, source_file:lines)
     - Claim record id for provenance walk
  4. Skipped-KSIs section for `not_applicable` / unknown-KSI entries.
"""

from __future__ import annotations

from datetime import datetime

from jinja2 import Environment, select_autoescape

from efterlev.agents import DocumentationReport
from efterlev.reports.html import DRAFT_BANNER_HTML, render_base_document

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
# shared stylesheet for a report-local concern.
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
  /* Visual distinction for manifest-sourced Evidence (human-signed
     procedural attestations vs. scanner-derived detector output). No
     badge for detector Evidence — detectors are the default; the badge
     is only needed to mark the exceptional case. Colors chosen to echo
     the DRAFT banner's amber family so the human reviewer's eye
     immediately lands on human-signed content. */
  .source-badge {
    display: inline-block;
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    padding: 1px 6px;
    margin-left: 4px;
    border-radius: 3px;
    vertical-align: middle;
  }
  .source-badge.source-manifest {
    background: #fff4d6;
    color: #7a5200;
    border: 1px solid #e0c88a;
  }
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
