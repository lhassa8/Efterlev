"""HTML rendering for `GapReport` artifacts.

One function entry point, `render_gap_report_html`, takes a typed
`GapReport` (the Gap Agent's output) plus its baseline/FRMR metadata
and returns a complete HTML document ready to write to disk or serve.

Layout:
  1. Header + baseline metadata.
  2. "DRAFT — requires human review" banner (KSI classifications are
     Claims, not Evidence).
  3. Summary table: KSI id | status pill | rationale one-liner.
  4. Per-KSI sections with full rationale, status pill, and the list of
     cited evidence IDs (linked by fence format so a later HTML report
     that links into the provenance store can pick them up).
  5. Separate "Unmapped findings" section for evidence records whose
     ksis_evidenced=[] (the SC-28 case per DECISIONS design call #1).

Jinja is used just for the body fragment — the document shell comes
from `html.render_base_document`. This keeps the template small and
the HTML deterministic enough for test snapshots.
"""

from __future__ import annotations

from datetime import datetime

from jinja2 import Environment, select_autoescape
from markupsafe import Markup

from efterlev.agents import GapReport
from efterlev.reports.html import DRAFT_BANNER_HTML, render_base_document

_BODY_TEMPLATE = """
{{ draft_banner }}

<p class="meta">
  Baseline: <code>{{ baseline_id }}</code> ·
  FRMR: <code>{{ frmr_version }}</code> ·
  KSIs classified: <strong>{{ classifications | length }}</strong>
  {% if unmapped_findings %}·
  Unmapped findings: <strong>{{ unmapped_findings | length }}</strong>{% endif %}
</p>

<h2>Summary</h2>
<table>
  <thead>
    <tr><th>KSI</th><th>Status</th><th>Rationale</th></tr>
  </thead>
  <tbody>
  {% for clf in classifications %}
    <tr>
      <td><span class="ksi-id">{{ clf.ksi_id }}</span></td>
      <td>
        <span class="status-pill status-{{ clf.status }}">
          {{ clf.status | replace('_', ' ') }}
        </span>
      </td>
      <td>{{ clf.rationale | truncate(140, killwords=True) }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>

<h2>Classifications</h2>
{% for clf in classifications %}
<div class="record claim">
  <h3>
    <span class="ksi-id">{{ clf.ksi_id }}</span>
    <span class="status-pill status-{{ clf.status }}">{{ clf.status | replace('_', ' ') }}</span>
  </h3>
  <div class="rationale">{{ clf.rationale }}</div>
  {% if clf.evidence_ids %}
  <div class="evidence-links">
    Cites {{ clf.evidence_ids | length }} evidence record(s):
    {% for eid in clf.evidence_ids -%}
    <code class="fence-id">{{ eid }}</code>{% if not loop.last %}, {% endif %}
    {%- endfor %}
  </div>
  {% else %}
  <div class="evidence-links">No evidence cited.</div>
  {% endif %}
</div>
{% endfor %}

{% if unmapped_findings %}
<h2>Unmapped findings</h2>
<p class="meta">
  Evidence records that fire at the 800-53 level but do not currently
  map to any KSI in the vendored FRMR. Per DECISIONS 2026-04-21 design
  call #1, these are surfaced honestly rather than shoehorned into the
  nearest-thematic KSI.
</p>
{% for finding in unmapped_findings %}
<div class="record evidence">
  <h3>
    <span class="fence-id">{{ finding.evidence_id }}</span>
    <span class="ksi-id">{{ finding.controls | join(', ') }}</span>
  </h3>
  <div class="rationale">{{ finding.note }}</div>
</div>
{% endfor %}
{% endif %}

{% if claim_record_ids %}
<h2>Provenance record IDs</h2>
<p class="meta">
  Each classification was persisted as a Claim in the provenance store.
  Pass any of these IDs to <code>efterlev provenance show</code> to walk
  the chain back to the underlying .tf source lines.
</p>
<ul>
{% for rid in claim_record_ids %}
  <li><code class="record-id">{{ rid }}</code></li>
{% endfor %}
</ul>
{% endif %}
"""


def render_gap_report_html(
    report: GapReport,
    *,
    baseline_id: str,
    frmr_version: str,
    generated_at: datetime | None = None,
) -> str:
    """Return a complete HTML document rendering of a GapReport."""
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(_BODY_TEMPLATE)
    body = template.render(
        classifications=report.ksi_classifications,
        unmapped_findings=report.unmapped_findings,
        claim_record_ids=report.claim_record_ids,
        baseline_id=baseline_id,
        frmr_version=frmr_version,
        draft_banner=DRAFT_BANNER_HTML,
    )

    when = (generated_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    return render_base_document(
        title="Gap Report",
        subtitle=(
            f"{len(report.ksi_classifications)} KSI classification(s), "
            f"{len(report.unmapped_findings)} unmapped finding(s)"
        ),
        body_html=Markup(body),
        generated_at=when,
    )
