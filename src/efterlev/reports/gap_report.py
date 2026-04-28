"""HTML + JSON rendering for `GapReport` artifacts.

`render_gap_report_html` returns a complete HTML document; the parallel
`render_gap_report_json` returns the same data as a JSON-serializable
dict. The CLI writes both side-by-side (`gap-<ts>.html` +
`gap-<ts>.json`) so downstream tooling consumers (3PAO ingest, custom
dashboards) can read the data without scraping HTML.

HTML layout:
  1. Header + baseline metadata.
  2. "DRAFT — requires human review" banner (KSI classifications are
     Claims, not Evidence).
  3. Summary table: KSI id | status pill | rationale one-liner.
  4. Per-KSI sections with full rationale, status pill, and the list of
     cited evidence IDs (linked by fence format so a later HTML report
     that links into the provenance store can pick them up).
  5. Separate "Unmapped findings" section for evidence records whose
     ksis_evidenced=[] (the SC-28 case per DECISIONS design call #1).

JSON schema (v1):
  {
    "schema_version": "1.0",
    "report_type": "gap",
    "generated_at": "<iso-8601>",
    "baseline_id": "<str>",
    "frmr_version": "<str>",
    "workspace_boundary_state": "<state>",
    "ksi_classifications": [
      {
        "ksi_id": "<str>", "status": "<status>", "rationale": "<str>",
        "evidence_ids": ["<id>", ...],
        "boundary_state": "<state>"
      },
      ...
    ],
    "unmapped_findings": [
      {"evidence_id": "<id>", "controls": ["<id>", ...], "note": "<str>"}
    ],
    "claim_record_ids": ["<id>", ...]
  }

Jinja is used just for the HTML body fragment — the document shell
comes from `html.render_base_document`. JSON serialization uses Pydantic
model_dump for the typed sub-records to keep field names canonical.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import Environment, select_autoescape

from efterlev.agents import GapReport
from efterlev.models import Evidence, Indicator, Theme
from efterlev.reports.html import DRAFT_BANNER_HTML, render_base_document

GAP_REPORT_JSON_SCHEMA_VERSION = "1.0"

# Filter-by-status pills + small vanilla-JS handler. No framework, no
# external CDN, no analytics — Priority 2's "self-contained" + "no
# framework" requirement. With JS disabled, the buttons render but
# clicking does nothing and all cards/rows remain visible
# (progressive enhancement: degrades to "all results visible, sorted
# by KSI").
_FILTER_CSS_JS = """
<style>
  .filter-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin: 12px 0 16px 0;
    padding: 10px 12px;
    background: #fbfcfd;
    border: 1px solid #e3e8ef;
    border-radius: 6px;
  }
  .filter-bar-label {
    font-size: 12px;
    color: #4a4a4a;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-transform: uppercase;
    margin-right: 4px;
  }
  .filter-btn {
    cursor: pointer;
    border: 1px solid #d3d8e0;
    background: #ffffff;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 12px;
    color: #1a1a1a;
    transition: background 0.04s ease, border-color 0.04s ease;
  }
  .filter-btn:hover { border-color: #0a2540; }
  .filter-btn.active {
    background: #0a2540;
    border-color: #0a2540;
    color: #ffffff;
  }
  .search-input {
    flex: 1 1 240px;
    min-width: 200px;
    margin-left: auto;
    padding: 5px 10px;
    font-size: 13px;
    border: 1px solid #d3d8e0;
    border-radius: 4px;
    background: #ffffff;
    color: #1a1a1a;
  }
  .search-input:focus {
    outline: none;
    border-color: #0a2540;
    box-shadow: 0 0 0 2px rgba(10, 37, 64, 0.12);
  }
  .search-count {
    font-size: 12px;
    color: #4a4a4a;
    font-variant-numeric: tabular-nums;
    min-width: 60px;
    text-align: right;
  }
  /* Filter and search hide independently — both apply display:none.
     Either condition hides the element. */
  .filter-hidden, .search-hidden { display: none !important; }
</style>
<script>
(function () {
  var bar = document.querySelector('.filter-bar');
  if (!bar) return;
  var btns = bar.querySelectorAll('.filter-btn');
  var searchInput = bar.querySelector('#card-search');
  var searchCount = bar.querySelector('#search-count');

  btns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var status = btn.getAttribute('data-status');
      btns.forEach(function (b) { b.classList.toggle('active', b === btn); });
      var targets = document.querySelectorAll('[data-status]');
      targets.forEach(function (el) {
        if (el.classList.contains('filter-btn')) return;
        if (status === 'all' || el.getAttribute('data-status') === status) {
          el.classList.remove('filter-hidden');
        } else {
          el.classList.add('filter-hidden');
        }
      });
    });
  });

  if (searchInput) {
    var debounce = null;
    searchInput.addEventListener('input', function () {
      clearTimeout(debounce);
      debounce = setTimeout(applySearch, 80);
    });
  }

  function applySearch() {
    var q = (searchInput ? searchInput.value || '' : '').trim().toLowerCase();
    var targets = document.querySelectorAll('.record.claim, tr[data-status]');
    var visible = 0;
    var total = 0;
    targets.forEach(function (el) {
      total += 1;
      var text = (el.textContent || '').toLowerCase();
      if (q === '' || text.indexOf(q) !== -1) {
        el.classList.remove('search-hidden');
        if (!el.classList.contains('filter-hidden')) visible += 1;
      } else {
        el.classList.add('search-hidden');
      }
    });
    if (searchCount) {
      searchCount.textContent = q === ''
        ? ''
        : visible + ' / ' + total + ' match';
    }
  }
})();
</script>
"""

# Coverage-matrix CSS, prepended to the body fragment. Self-contained;
# uses the existing .status-* color palette from the base stylesheet so
# the matrix legend pills match the per-KSI status pills below.
_COVERAGE_MATRIX_CSS = """
<style>
  .coverage-matrix {
    margin: 8px 0 24px 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .matrix-theme {
    border: 1px solid #e3e8ef;
    border-radius: 6px;
    padding: 10px 12px;
    background: #fbfcfd;
  }
  .matrix-theme-header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 8px;
    font-size: 13px;
  }
  .matrix-theme-id {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-weight: 700;
    color: #0a2540;
    background: #eaeef2;
    padding: 1px 8px;
    border-radius: 3px;
  }
  .matrix-theme-name { color: #1a1a1a; }
  .matrix-theme-counts {
    margin-left: auto;
    font-size: 12px;
    color: #4a4a4a;
  }
  .matrix-theme-cells {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .matrix-cell {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 52px;
    padding: 4px 8px;
    border-radius: 4px;
    text-decoration: none;
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.3px;
    border: 1px solid transparent;
    transition: transform 0.04s ease;
  }
  .matrix-cell:hover { transform: translateY(-1px); border-color: #0a2540; }
  .matrix-cell.status-implemented    { background: #d1f4da; color: #0a4a17; }
  .matrix-cell.status-partial        { background: #fff2c2; color: #6a4e00; }
  .matrix-cell.status-not_implemented { background: #fddede; color: #7a1f1f; }
  .matrix-cell.status-not_applicable { background: #eaeef2; color: #444c56; }
  .matrix-cell.status-evidence_layer_inapplicable {
    background: #d6e5fa; color: #0a3a7a;
  }
  .matrix-cell.status-unclassified {
    background: #f5f6f8; color: #6a737d; border-color: #e3e8ef;
  }
  .matrix-cell-suffix {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  .matrix-legend { margin: -4px 0 12px 0; }
  .matrix-cell-legend {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 3px;
    margin-left: 6px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-transform: uppercase;
  }
  .matrix-cell-legend.status-unclassified {
    background: #f5f6f8; color: #6a737d; border: 1px solid #e3e8ef;
  }
</style>
"""

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

{% if coverage_matrix %}
<h2>Coverage matrix</h2>
<p class="meta matrix-legend">
  Every cell is one KSI; color = the Gap Agent's classification.
  <span class="matrix-cell-legend status-implemented">implemented</span>
  <span class="matrix-cell-legend status-partial">partial</span>
  <span class="matrix-cell-legend status-not_implemented">not implemented</span>
  <span class="matrix-cell-legend status-evidence_layer_inapplicable"
        >evidence layer inapplicable</span>
  <span class="matrix-cell-legend status-not_applicable">not applicable</span>
  <span class="matrix-cell-legend status-unclassified">unclassified</span>
</p>
<div class="coverage-matrix">
{% for theme in coverage_matrix %}
  <div class="matrix-theme">
    <div class="matrix-theme-header">
      <span class="matrix-theme-id">{{ theme.id }}</span>
      <span class="matrix-theme-name">{{ theme.name }}</span>
      <span class="matrix-theme-counts">
        {{ theme.classified_count }} / {{ theme.ksis | length }} classified
      </span>
    </div>
    <div class="matrix-theme-cells">
      {% for cell in theme.ksis %}
      <a class="matrix-cell status-{{ cell.status }}"
         href="#{{ cell.anchor }}"
         title="{{ cell.id }} — {{ cell.name }} — {{ cell.status | replace('_', ' ') }}">
        <span class="matrix-cell-suffix">{{ cell.suffix }}</span>
      </a>
      {% endfor %}
    </div>
  </div>
{% endfor %}
</div>
{% endif %}

<h2>Summary</h2>
<table>
  <thead>
    <tr><th>KSI</th><th>Status</th><th>Boundary</th><th>Rationale</th></tr>
  </thead>
  <tbody>
  {% for clf in classifications %}
    <tr data-status="{{ clf.status }}">
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

{% if classifications %}
<h2>Classifications</h2>
<div class="filter-bar" role="toolbar" aria-label="Filter classifications">
  <span class="filter-bar-label">Show:</span>
  <button class="filter-btn active" data-status="all">All</button>
  <button class="filter-btn" data-status="implemented">Implemented</button>
  <button class="filter-btn" data-status="partial">Partial</button>
  <button class="filter-btn" data-status="not_implemented">Not implemented</button>
  <button class="filter-btn"
          data-status="evidence_layer_inapplicable">Evidence-layer inapplicable</button>
  <button class="filter-btn" data-status="not_applicable">Not applicable</button>
  <input type="search"
         id="card-search"
         class="search-input"
         placeholder="Search KSI, control, detector, rationale, evidence id..."
         aria-label="Search classifications" />
  <span class="search-count" id="search-count" aria-live="polite"></span>
</div>
{% endif %}
{% for clf in classifications %}
{% set bs = classification_boundary_state.get(clf.ksi_id, 'boundary_undeclared') %}
{% if bs == "out_of_boundary" %}
<details class="record claim out-of-boundary-collapsed"
         id="ksi-{{ clf.ksi_id }}"
         data-status="{{ clf.status }}">
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
<div class="record claim" id="ksi-{{ clf.ksi_id }}" data-status="{{ clf.status }}">
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
    themes: dict[str, Theme] | None = None,
    indicators: dict[str, Indicator] | None = None,
) -> str:
    """Return a complete HTML document rendering of a GapReport.

    Pass `evidence` (the same list the agent reasoned over) to get
    per-citation source badges — manifest-sourced citations render with
    an "attestation" pill so reviewers can tell human-signed evidence
    from scanner-derived evidence at a glance. When `evidence` is None
    or empty, citations render without badges (scanner-only default).

    Pass `themes` + `indicators` (from `FrmrDocument.themes` /
    `FrmrDocument.indicators`) to render the coverage matrix at the top:
    one cell per KSI in the FRMR baseline, color-coded by classification
    status. KSIs the agent didn't classify show as "unclassified" (gray).
    Cells link via anchor to the per-KSI classification card below.

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
    coverage_matrix = build_coverage_matrix(report, themes, indicators)

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
        coverage_matrix=coverage_matrix,
    )

    when = (generated_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    return render_base_document(
        title="Gap Report",
        subtitle=(
            f"{len(report.ksi_classifications)} KSI classification(s), "
            f"{len(report.unmapped_findings)} unmapped finding(s)"
        ),
        body_html=_COVERAGE_MATRIX_CSS + _FILTER_CSS_JS + body,
        generated_at=when,
    )


def render_gap_report_json(
    report: GapReport,
    *,
    baseline_id: str,
    frmr_version: str,
    evidence: list[Evidence] | None = None,
    generated_at: datetime | None = None,
    themes: dict[str, Theme] | None = None,
    indicators: dict[str, Indicator] | None = None,
) -> dict[str, Any]:
    """Return the gap report as a JSON-serializable dict.

    Mirrors `render_gap_report_html`'s data view but emits a
    schema-versioned, machine-readable structure suitable for tool
    integration. Pass to `json.dumps` with `sort_keys=True, indent=2`
    for the canonical sidecar shape.

    The boundary-state derivation is identical to the HTML renderer's:
    each classification is annotated with the worst-case boundary state
    across its cited evidence (with `in_boundary` winning when present).

    Pass `themes` + `indicators` to include the coverage matrix in the
    sidecar — same data the HTML renders, structured for JS-driven UIs
    or 3PAO ingest tooling that wants the full theme x KSI grid.
    """
    evidence_list = evidence or []
    evidence_boundary_state: dict[str, str] = {
        ev.evidence_id: ev.boundary_state for ev in evidence_list
    }
    classification_boundary_state = _resolve_classification_boundary_states(
        report, evidence_boundary_state
    )
    workspace_boundary_state = _resolve_workspace_boundary_state(evidence_boundary_state)
    when = (generated_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    matrix = build_coverage_matrix(report, themes, indicators)

    return {
        "schema_version": GAP_REPORT_JSON_SCHEMA_VERSION,
        "report_type": "gap",
        "generated_at": when,
        "baseline_id": baseline_id,
        "frmr_version": frmr_version,
        "workspace_boundary_state": workspace_boundary_state,
        "ksi_classifications": [
            {
                "ksi_id": clf.ksi_id,
                "status": clf.status,
                "rationale": clf.rationale,
                "evidence_ids": list(clf.evidence_ids),
                "boundary_state": classification_boundary_state.get(
                    clf.ksi_id, "boundary_undeclared"
                ),
            }
            for clf in report.ksi_classifications
        ],
        "unmapped_findings": [
            {
                "evidence_id": uf.evidence_id,
                "controls": list(uf.controls),
                "note": uf.note,
            }
            for uf in report.unmapped_findings
        ],
        "claim_record_ids": list(report.claim_record_ids),
        "coverage_matrix": matrix,
    }


def build_coverage_matrix(
    report: GapReport,
    themes: dict[str, Theme] | None,
    indicators: dict[str, Indicator] | None,
) -> list[dict[str, Any]] | None:
    """Build the coverage-matrix data structure: themes x KSIs x status.

    Returns None when `themes` or `indicators` is missing — the renderer
    treats that as "no matrix" and omits the section. Otherwise returns
    one entry per theme, with a sorted list of KSI cells per theme:

      [
        {
          "id": "<theme_id>",
          "name": "<theme name>",
          "ksis": [
            {
              "id": "<KSI-XX-XXX>",
              "name": "<KSI name>",
              "suffix": "<XXX>",
              "status": "<status | unclassified>",
              "anchor": "ksi-<KSI-XX-XXX>"
            },
            ...
          ],
          "classified_count": <int>
        },
        ...
      ]

    KSIs the agent classified are mapped to their actual status; KSIs in
    the FRMR baseline that the agent didn't touch land in
    `status="unclassified"` (rendered with a neutral-gray cell).
    """
    if not themes or not indicators:
        return None

    status_by_ksi: dict[str, str] = {clf.ksi_id: clf.status for clf in report.ksi_classifications}

    out: list[dict[str, Any]] = []
    for theme_id in sorted(themes):
        theme = themes[theme_id]
        ksis_in_theme = sorted(
            (ind for ind in indicators.values() if ind.theme == theme_id),
            key=lambda i: i.id,
        )
        if not ksis_in_theme:
            continue
        cells: list[dict[str, Any]] = []
        classified_count = 0
        for ind in ksis_in_theme:
            status = status_by_ksi.get(ind.id, "unclassified")
            if status != "unclassified":
                classified_count += 1
            # The KSI suffix — last 3 chars after the second hyphen.
            # "KSI-SVC-SNT" → "SNT". Falls back to the full id if the
            # shape is unexpected.
            parts = ind.id.split("-", 2)
            suffix = parts[2] if len(parts) == 3 else ind.id
            cells.append(
                {
                    "id": ind.id,
                    "name": ind.name,
                    "suffix": suffix,
                    "status": status,
                    "anchor": f"ksi-{ind.id}",
                }
            )
        out.append(
            {
                "id": theme.id,
                "name": theme.name,
                "ksis": cells,
                "classified_count": classified_count,
            }
        )
    return out


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
