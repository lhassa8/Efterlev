"""HTML rendering for `RemediationProposal` artifacts.

Companion to `gap_report.py` and `documentation_report.py`. Single-KSI
output: one card containing the proposed Terraform diff (or an empty-diff
"procedural gap" note), the explanation, cited evidence + source files,
and the claim record id for provenance walks.

Layout:
  1. Header + KSI id + status pill (proposed / no_terraform_fix).
  2. "DRAFT — requires human review" banner. Diffs are Claims — the agent
     generated them, a human applies them. Efterlev never touches the repo.
  3. Explanation body (prose, paragraph breaks preserved).
  4. Diff block, rendered in a monospace `<pre>` with syntax-agnostic
     styling (leading `+`/`-`/`@@` lines get color hints via simple CSS).
     If the diff is empty the card shows "No Terraform remediation; see
     explanation for recommended action."
  5. Cited evidence IDs.
  6. Cited source files the diff touches.
  7. Claim record id for `provenance show`.
"""

from __future__ import annotations

from datetime import datetime

from jinja2 import Environment, select_autoescape

from efterlev.agents import RemediationProposal
from efterlev.reports.html import DRAFT_BANNER_HTML, render_base_document

_BODY_TEMPLATE = """
{{ draft_banner }}

<p class="meta">
  KSI: <span class="ksi-id">{{ proposal.ksi_id }}</span> ·
  Status: <span class="status-pill remediation-{{ proposal.status }}">
    {{ proposal.status | replace('_', ' ') }}
  </span>
</p>

<div class="record claim">
  <h2>Proposed remediation</h2>

  <div class="explanation">{{ proposal.explanation }}</div>

  {% if proposal.diff %}
  <h3>Proposed diff</h3>
  <pre class="diff"><code>{{ proposal.diff }}</code></pre>
  {% else %}
  <div class="no-diff">
    <strong>No Terraform remediation proposed.</strong>
    This gap is not closable through a Terraform change (it likely lives
    in a procedural or runtime layer — IdP configuration, AWS console
    settings, documented processes). See the explanation above for what
    a human should do instead.
  </div>
  {% endif %}

  {% if proposal.cited_source_files %}
  <div class="citations">
    <strong>Files touched ({{ proposal.cited_source_files | length }}):</strong>
    <ul>
    {% for path in proposal.cited_source_files %}
      <li><code>{{ path }}</code></li>
    {% endfor %}
    </ul>
  </div>
  {% endif %}

  {% if proposal.cited_evidence_ids %}
  <div class="citations">
    <strong>Grounded in evidence ({{ proposal.cited_evidence_ids | length }}):</strong>
    <ul>
    {% for eid in proposal.cited_evidence_ids %}
      <li><code class="fence-id">{{ eid }}</code></li>
    {% endfor %}
    </ul>
  </div>
  {% endif %}

  {% if proposal.claim_record_id %}
  <div class="evidence-links">
    Provenance record: <code class="record-id">{{ proposal.claim_record_id }}</code>
  </div>
  {% endif %}
</div>

<h2>How to apply</h2>
<ol class="apply-steps">
  <li>
    <strong>Read the diff carefully</strong> — the agent proposed it; you
    decide whether it's the right shape. Look for identifiers the diff
    introduces but the shown source doesn't define (e.g. a new
    <code>var.kms_key_id</code>); those are yours to wire up.
  </li>
  <li>
    <strong>Save the diff to a file</strong> (e.g. <code>remediation.patch</code>)
    and run <code>git apply --check remediation.patch</code> to verify
    it applies cleanly. If not, fix the conflict manually — the diff is a
    draft grounded in the scanner's view, which may lag the tree.
  </li>
  <li>
    <strong>Test in a branch.</strong> Apply, run your usual Terraform plan,
    inspect the plan output, and only merge after review.
  </li>
  <li>
    <strong>Re-scan.</strong> Run <code>efterlev scan</code> and
    <code>efterlev agent gap</code> again; confirm this KSI's status
    improved.
  </li>
</ol>
"""

# Per-report CSS for diff rendering + status pills specific to remediation.
_REMEDIATION_CSS = """
<style>
  .explanation {
    white-space: pre-wrap;
    margin-top: 10px;
    margin-bottom: 16px;
    color: #1a1a1a;
    line-height: 1.55;
  }
  .diff {
    background: #0d1117;
    color: #e6edf3;
    padding: 14px 16px;
    border-radius: 6px;
    overflow-x: auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12.5px;
    line-height: 1.5;
    margin: 8px 0 16px 0;
  }
  .diff code { white-space: pre; color: inherit; background: transparent; }
  .no-diff {
    background: #eaeef2;
    border-left: 4px solid #6a737d;
    padding: 12px 16px;
    border-radius: 4px;
    margin: 12px 0;
    color: #1a1a1a;
  }
  .status-pill.remediation-proposed        { background: #d1f4da; color: #0a4a17; }
  .status-pill.remediation-no_terraform_fix { background: #fff2c2; color: #6a4e00; }

  .citations { margin-top: 12px; font-size: 13px; color: #4a4a4a; }
  .citations ul { margin: 6px 0 0 0; padding-left: 20px; }
  .citations li { margin-bottom: 3px; }
  .apply-steps { line-height: 1.7; color: #1a1a1a; }
  .apply-steps li { margin-bottom: 8px; }
</style>
"""


def render_remediation_proposal_html(
    proposal: RemediationProposal,
    *,
    generated_at: datetime | None = None,
) -> str:
    """Return a complete HTML document rendering of a RemediationProposal."""
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(_BODY_TEMPLATE)
    body = template.render(proposal=proposal, draft_banner=DRAFT_BANNER_HTML)

    when = (generated_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    return render_base_document(
        title=f"Remediation Proposal — {proposal.ksi_id}",
        subtitle=f"{proposal.status.replace('_', ' ').title()}",
        body_html=_REMEDIATION_CSS + body,
        generated_at=when,
    )
