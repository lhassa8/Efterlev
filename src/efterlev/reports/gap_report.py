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

from efterlev.agents import GapReport
from efterlev.models import Evidence
from efterlev.reports.html import DRAFT_BANNER_HTML, render_base_document

_BODY_TEMPLATE = """
{{ draft_banner }}

{% if workspace_boundary_state == "boundary_undeclared" and classifications %}
<div class="boundary-banner boundary-undeclared">
  <strong>FedRAMP boundary not declared for this workspace.</strong>
  Every finding flows through unfiltered. To produce a defensible
  posture statement to a 3PAO, declare scope:
  <code>efterlev boundary set --include 'boundary/**'</code>.
</div>
{% endif %}

<p class="meta">
  Baseline: <code>{{ baseline_id }}</code> ·
  FRMR: <code>{{ frmr_version }}</code> ·
  KSIs classified: <strong>{{ classifications | length }}</strong>
  {% if unmapped_findings %}·
  Unmapped findings: <strong>{{ unmapped_findings | length }}</strong>{% endif %}
  {% if workspace_boundary_state != "boundary_undeclared" %}·
  Boundary: <strong>{{ workspace_boundary_state | replace('_', ' ') }}</strong>{% endif %}
</p>

<h2>Summary</h2>
<table>
  <thead>
    <tr><th>KSI</th><th>Status</th><th>Boundary</th><th>Rationale</th></tr>
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
      <td>
        {% set bs = classification_boundary_state.get(clf.ksi_id, 'boundary_undeclared') %}
        <span class="boundary-pill boundary-{{ bs }}">
          {{ bs | replace('_', ' ') }}
        </span>
      </td>
      <td>{{ clf.rationale | truncate(140, killwords=True) }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>

<h2>Classifications</h2>
{% for clf in classifications %}
{% set bs = classification_boundary_state.get(clf.ksi_id, 'boundary_undeclared') %}
{% if bs == "out_of_boundary" %}
<details class="record claim out-of-boundary-collapsed">
  <summary>
    <span class="ksi-id">{{ clf.ksi_id }}</span>
    <span class="status-pill status-{{ clf.status }}">{{ clf.status | replace('_', ' ') }}</span>
    <span class="boundary-pill boundary-out_of_boundary">out of boundary</span>
    <span class="boundary-collapsed-hint">(click to expand)</span>
  </summary>
  <div class="rationale">{{ clf.rationale }}</div>
  {% if clf.evidence_ids %}
  <div class="evidence-links">
    Cites {{ clf.evidence_ids | length }} evidence record(s) — all out of declared boundary:
    {% for eid in clf.evidence_ids -%}
    <code class="fence-id">{{ eid }}</code>{% if detector_by_id.get(eid) == "manifest"
      %}<span class="source-badge source-manifest"
              title="Human-signed procedural attestation from .efterlev/manifests/"
              >attestation</span>{% endif %}{% if not loop.last %}, {% endif %}
    {%- endfor %}
  </div>
  {% endif %}
</details>
{% else %}
<div class="record claim">
  <h3>
    <span class="ksi-id">{{ clf.ksi_id }}</span>
    <span class="status-pill status-{{ clf.status }}">{{ clf.status | replace('_', ' ') }}</span>
    {% if bs != "boundary_undeclared" %}
    <span class="boundary-pill boundary-{{ bs }}">{{ bs | replace('_', ' ') }}</span>
    {% endif %}
  </h3>
  <div class="rationale">{{ clf.rationale }}</div>
  {% if clf.evidence_ids %}
  <div class="evidence-links">
    Cites {{ clf.evidence_ids | length }} evidence record(s):
    {% for eid in clf.evidence_ids -%}
    <code class="fence-id">{{ eid }}</code>{% if detector_by_id.get(eid) == "manifest"
      %}<span class="source-badge source-manifest"
              title="Human-signed procedural attestation from .efterlev/manifests/"
              >attestation</span>{% endif %}{% if not loop.last %}, {% endif %}
    {%- endfor %}
  </div>
  {% else %}
  <div class="evidence-links">No evidence cited.</div>
  {% endif %}
</div>
{% endif %}
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
    evidence: list[Evidence] | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Return a complete HTML document rendering of a GapReport.

    Pass `evidence` (the same list the agent reasoned over) to get
    per-citation source badges — manifest-sourced citations render with
    an "attestation" pill so reviewers can tell human-signed evidence
    from scanner-derived evidence at a glance. When `evidence` is None
    or empty, citations render without badges (scanner-only default).

    Boundary scoping (Priority 4.2, 2026-04-27): each Evidence carries a
    `boundary_state`. The renderer derives:
      - per-classification dominant state (worst-case across cited
        evidence; classifications with no cited evidence inherit the
        workspace state)
      - workspace state (what to show in the top banner)
    `out_of_boundary` classifications collapse under `<details>` so
    reviewers focus on in-scope findings; the workspace banner appears
    only when no evidence has a real boundary classification (i.e. the
    customer hasn't declared scope).
    """
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(_BODY_TEMPLATE)
    evidence_list = evidence or []
    detector_by_id: dict[str, str] = {ev.evidence_id: ev.detector_id for ev in evidence_list}
    evidence_boundary_state: dict[str, str] = {
        ev.evidence_id: ev.boundary_state for ev in evidence_list
    }
    classification_boundary_state = _resolve_classification_boundary_states(
        report, evidence_boundary_state
    )
    workspace_boundary_state = _resolve_workspace_boundary_state(evidence_boundary_state)

    body = template.render(
        classifications=report.ksi_classifications,
        unmapped_findings=report.unmapped_findings,
        claim_record_ids=report.claim_record_ids,
        baseline_id=baseline_id,
        frmr_version=frmr_version,
        draft_banner=DRAFT_BANNER_HTML,
        detector_by_id=detector_by_id,
        classification_boundary_state=classification_boundary_state,
        workspace_boundary_state=workspace_boundary_state,
    )

    when = (generated_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    return render_base_document(
        title="Gap Report",
        subtitle=(
            f"{len(report.ksi_classifications)} KSI classification(s), "
            f"{len(report.unmapped_findings)} unmapped finding(s)"
        ),
        body_html=body,
        generated_at=when,
    )


def _resolve_classification_boundary_states(
    report: GapReport,
    evidence_boundary_state: dict[str, str],
) -> dict[str, str]:
    """For each classification, compute a single boundary-state label.

    Rule: if ANY cited evidence is `in_boundary`, the classification is
    `in_boundary` (worth surfacing). If ALL cited evidence is
    `out_of_boundary`, the classification is `out_of_boundary` (collapse it).
    Mixed `out_of_boundary` + `boundary_undeclared` → `boundary_undeclared`
    (don't drop a finding the customer might still need to see).
    Classifications with no cited evidence inherit the workspace's
    aggregate state — they're "real gaps" rather than findings tied to a
    specific in/out resource.
    """
    workspace_state = _resolve_workspace_boundary_state(evidence_boundary_state)
    out: dict[str, str] = {}
    for clf in report.ksi_classifications:
        if not clf.evidence_ids:
            out[clf.ksi_id] = workspace_state
            continue
        states = [
            evidence_boundary_state.get(eid, "boundary_undeclared") for eid in clf.evidence_ids
        ]
        if any(s == "in_boundary" for s in states):
            out[clf.ksi_id] = "in_boundary"
        elif all(s == "out_of_boundary" for s in states):
            out[clf.ksi_id] = "out_of_boundary"
        else:
            out[clf.ksi_id] = "boundary_undeclared"
    return out


def _resolve_workspace_boundary_state(evidence_boundary_state: dict[str, str]) -> str:
    """The workspace is `boundary_undeclared` iff every Evidence is undeclared
    (i.e. no `[boundary]` config). Any in/out_of_boundary evidence implies
    the workspace has a declaration."""
    if not evidence_boundary_state:
        return "boundary_undeclared"
    if all(s == "boundary_undeclared" for s in evidence_boundary_state.values()):
        return "boundary_undeclared"
    # Workspace has a declaration; return whatever the dominant state is.
    # For the banner, only "boundary_undeclared" matters; anything else
    # suppresses the banner. We pick "in_boundary" for downstream
    # determinism (used in the meta line).
    return "in_boundary"
