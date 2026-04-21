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
