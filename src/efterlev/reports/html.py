"""Shared HTML scaffolding for every Efterlev report.

`render_base_document(title, body_html)` wraps a body fragment in a
complete HTML document with the Evidence/Claims stylesheet baked in.
Per-report renderers in sibling modules compose their body via Jinja
and pass the rendered string here.

The CSS is intentionally minimal and inlined into `<style>` — no
external stylesheet, no web fonts, no framework. The output must
survive being emailed, attached, or archived in airgapped environments.
Content width caps at 960px for readability.

Design commitments baked into the stylesheet:
  - Evidence records render in a `.evidence` card with a green left
    border and "Deterministic scanner output" subtitle.
  - Claims (classifications, narratives, remediations) render in a
    `.claim` card with an amber left border and a "DRAFT — requires
    human review" banner.
  - Status pills (.status-implemented / .status-partial / ...) are
    color-coded to match what a FedRAMP 3PAO expects.
"""

from __future__ import annotations

from markupsafe import Markup, escape

RECORDS_STYLESHEET = """
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: #1a1a1a;
  background: #f5f5f7;
  margin: 0;
  padding: 24px;
}
.container { max-width: 960px; margin: 0 auto; }
h1, h2, h3 { color: #0a2540; margin-top: 0; }
h1 { font-size: 24px; border-bottom: 1px solid #d0d7de; padding-bottom: 8px; }
h2 { font-size: 18px; margin-top: 32px; }
h3 { font-size: 15px; margin-top: 0; }
.meta { color: #6a737d; font-size: 13px; margin-bottom: 24px; }
.meta code { background: #eaeef2; padding: 1px 4px; border-radius: 3px; font-size: 12px; }

.draft-banner {
  background: #fff3cd;
  border: 1px solid #f0c36d;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 24px;
  color: #72570e;
  font-weight: 600;
}

.record {
  background: white;
  border-radius: 6px;
  padding: 16px 20px;
  margin-bottom: 12px;
  border-left: 4px solid #d0d7de;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.record.evidence { border-left-color: #1a7f37; }
.record.evidence::before {
  content: "Evidence — deterministic scanner output";
  display: block;
  font-size: 11px;
  color: #1a7f37;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.record.claim { border-left-color: #bf8700; }
.record.claim::before {
  content: "Claim — DRAFT, requires human review";
  display: block;
  font-size: 11px;
  color: #bf8700;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.status-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}
.status-implemented    { background: #d1f4da; color: #0a4a17; }
.status-partial        { background: #fff2c2; color: #6a4e00; }
.status-not_implemented { background: #fddede; color: #7a1f1f; }
.status-not_applicable { background: #eaeef2; color: #444c56; }
/* SPEC-57.1: distinct from not_implemented — blue rather than red,
   so a reviewer scanning the report can immediately see which "not
   covered" rows are real gaps vs scanner-coverage gaps. */
.status-evidence_layer_inapplicable { background: #d6e5fa; color: #0a3a7a; }

.ksi-id, .record-id, .fence-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: #0a2540;
  background: #eaeef2;
  padding: 1px 6px;
  border-radius: 3px;
}

.rationale { margin-top: 8px; color: #1a1a1a; }
.evidence-links { margin-top: 10px; font-size: 12px; color: #6a737d; }
.evidence-links code { font-size: 11px; }

/* Source-distinction badge. Manifest-sourced Evidence is human-signed
   procedural attestation (detector_id="manifest"); scanner-derived
   Evidence is the default and is unbadged. Amber to echo the DRAFT
   banner family and draw the reviewer's eye. See Phase 1 polish and
   Phase 2 (post-review fixup E). */
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

/* Authorization-boundary indicators (Priority 4.2, 2026-04-27).
   A boundary-pill is a sibling visual to status-pill — it answers a
   different question ("is this finding inside the customer's declared
   FedRAMP scope?") so it lives on its own dimension. */
.boundary-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  margin-left: 6px;
}
.boundary-in_boundary       { background: #e0f0ff; color: #0a3a7a; }
.boundary-out_of_boundary   { background: #f0e0e0; color: #5a3a3a; }
.boundary-boundary_undeclared { background: #f0f0f0; color: #555; }

/* Workspace-level banner shown when no boundary is declared. Placed
   above the meta line so a reviewer immediately sees the scope caveat. */
.boundary-banner {
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 1.5;
}
.boundary-banner.boundary-undeclared {
  background: #f3eef9;
  border: 1px solid #c8b3e0;
  color: #3e2d6a;
}
.boundary-banner code {
  background: #ffffff;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}

/* Out-of-boundary classifications collapse under <details>. The summary
   row carries the same status + boundary pills so a reviewer scanning
   collapsed sections sees what they'd skip. */
details.out-of-boundary-collapsed {
  background: #fafbfd;
  border-color: #d0d7de;
}
details.out-of-boundary-collapsed > summary {
  cursor: pointer;
  padding: 8px 12px;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
}
details.out-of-boundary-collapsed > summary::-webkit-details-marker { display: none; }
details.out-of-boundary-collapsed > summary::before {
  content: "▸";
  font-size: 11px;
  color: #6a737d;
}
details[open].out-of-boundary-collapsed > summary::before {
  content: "▾";
}
.boundary-collapsed-hint {
  font-size: 11px;
  color: #6a737d;
  font-style: italic;
  margin-left: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #eaeef2; }
th { background: #f6f8fa; font-weight: 600; font-size: 13px; color: #4a4a4a; }
tr:last-child td { border-bottom: none; }

.footer { margin-top: 32px; font-size: 12px; color: #6a737d; text-align: center; }

/* Print stylesheet (Priority 2.7, 2026-04-28). Hide interactive bits;
   ensure cards flow cleanly on paper without splitting across pages.
   The matrix and classification cards are the substance and stay. */
@media print {
  body {
    background: #ffffff;
    padding: 12px;
    font-size: 11pt;
    color: #000000;
  }
  .container { max-width: 100%; }
  /* Interactive bits — no clicking on paper. */
  .filter-bar { display: none !important; }
  /* Drop background tints + shadows; the card border-left is the
     visual anchor and survives well on paper. */
  .record {
    box-shadow: none;
    background: #ffffff;
    page-break-inside: avoid;
    break-inside: avoid;
  }
  table { box-shadow: none; }
  /* Hyperlinks render as plain text on paper; the URL fragment in the
     matrix anchors is meaningless without a browser. */
  a.matrix-cell { color: inherit; text-decoration: none; }
  a.matrix-cell:hover { transform: none; border-color: transparent; }
  /* Out-of-boundary <details> render expanded on paper so reviewers
     can see what was hidden in interactive viewing. */
  details.out-of-boundary-collapsed > summary::before { content: ""; }
  details.out-of-boundary-collapsed { background: #ffffff; }
  details.out-of-boundary-collapsed > summary { padding: 0; }
  details.out-of-boundary-collapsed > *:not(summary) { display: block !important; }
  /* Don't split a status pill or KSI cell across pages. */
  .status-pill, .matrix-cell, .ksi-id { page-break-inside: avoid; }
  h1, h2, h3 { page-break-after: avoid; }
  .footer { page-break-before: avoid; }
}
"""

DRAFT_BANNER_HTML = Markup(
    '<div class="draft-banner">'
    "DRAFT — requires human review. Every classification below was produced by "
    "an LLM reasoning over deterministic scanner evidence. A 3PAO or human "
    "reviewer must corroborate each claim before submission."
    "</div>"
)


def render_base_document(
    *,
    title: str,
    body_html: str | Markup,
    generated_at: str,
    subtitle: str | None = None,
) -> str:
    """Wrap a body fragment in a complete HTML document.

    `body_html` is trusted (already escaped by the caller's Jinja
    templates); the title / subtitle / generated_at are escaped here.
    """
    safe_title = escape(title)
    safe_subtitle = f"<p class='meta'>{escape(subtitle)}</p>" if subtitle else ""
    safe_generated = escape(generated_at)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{safe_title} — Efterlev</title>
  <style>{RECORDS_STYLESHEET}</style>
</head>
<body>
  <div class="container">
    <h1>{safe_title}</h1>
    {safe_subtitle}
    {body_html}
    <p class="footer">
      Generated by Efterlev at {safe_generated}.
      Drafts only — Efterlev does not produce ATOs.
    </p>
  </div>
</body>
</html>
"""
