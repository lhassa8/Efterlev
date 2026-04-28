"""Diff between two Gap-Report JSON sidecars.

Priority 2.10a (2026-04-28) added the pure-function `compute_gap_diff`
that takes two JSON-sidecar dicts (from `render_gap_report_json`) and
produces a structured `GapDiff`. Priority 2.10b (2026-04-28) adds
`render_gap_diff_html` to render that diff as an HTML page; the CLI's
`efterlev report diff` command drives it.

The diff computation is reusable from the MCP server, agent prompts
that reason about regression, and the eventual Drift Agent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from jinja2 import Environment, select_autoescape
from pydantic import BaseModel, ConfigDict, Field

from efterlev.reports.html import render_base_document

GapDiffOutcome = Literal[
    "added",  # KSI in current, not in prior
    "removed",  # KSI in prior, not in current
    "status_changed",  # KSI in both with different status
    "unchanged",  # KSI in both with same status
]


class KsiDiffEntry(BaseModel):
    """One KSI's diff outcome between two scans.

    For `status_changed`, both `prior_status` and `current_status` are
    populated. For `added`, only `current_status`. For `removed`, only
    `prior_status`. For `unchanged`, both are populated and equal.
    """

    model_config = ConfigDict(frozen=True)

    ksi_id: str
    outcome: GapDiffOutcome
    prior_status: str | None = None
    current_status: str | None = None
    # Human-friendly relative-severity label for `status_changed` rows:
    # "improved" (good→better), "regressed" (good→worse), or "shifted"
    # (lateral move, e.g. partial→evidence_layer_inapplicable). Filled
    # only on `status_changed`.
    severity_movement: Literal["improved", "regressed", "shifted"] | None = None


class GapDiff(BaseModel):
    """Diff between two Gap-Report JSON sidecars."""

    model_config = ConfigDict(frozen=True)

    prior_generated_at: str | None = None
    current_generated_at: str | None = None
    prior_baseline_id: str | None = None
    current_baseline_id: str | None = None
    entries: list[KsiDiffEntry] = Field(default_factory=list)

    @property
    def added(self) -> list[KsiDiffEntry]:
        return [e for e in self.entries if e.outcome == "added"]

    @property
    def removed(self) -> list[KsiDiffEntry]:
        return [e for e in self.entries if e.outcome == "removed"]

    @property
    def status_changed(self) -> list[KsiDiffEntry]:
        return [e for e in self.entries if e.outcome == "status_changed"]

    @property
    def unchanged(self) -> list[KsiDiffEntry]:
        return [e for e in self.entries if e.outcome == "unchanged"]

    @property
    def improved(self) -> list[KsiDiffEntry]:
        return [e for e in self.entries if e.severity_movement == "improved"]

    @property
    def regressed(self) -> list[KsiDiffEntry]:
        return [e for e in self.entries if e.severity_movement == "regressed"]


# Severity ranking for the relative-movement label. Lower rank = more
# actionable / "worse" posture. So a rank-increase = improvement.
# `not_applicable` and `evidence_layer_inapplicable` are higher than
# `implemented` because they declare the question is moot rather than
# answered, so a move *from* them *to* implemented is also "improved"
# in coverage terms — but the rank ordering primarily matters for
# distinguishing the actionable {not_implemented, partial} cluster
# from the rest.
_SEVERITY_RANK: dict[str, int] = {
    "not_implemented": 0,
    "partial": 1,
    "implemented": 2,
    "evidence_layer_inapplicable": 3,
    "not_applicable": 4,
}


def compute_gap_diff(prior: dict[str, Any], current: dict[str, Any]) -> GapDiff:
    """Compute a structured diff between two gap-report JSON sidecars.

    Both inputs must be the dict shape `render_gap_report_json` emits
    (schema_version "1.0" or compatible). Validates the report_type is
    "gap" and raises ValueError on mismatch.
    """
    _validate_input(prior, "prior")
    _validate_input(current, "current")

    prior_by_ksi: dict[str, str] = {
        clf["ksi_id"]: clf["status"] for clf in prior.get("ksi_classifications", [])
    }
    current_by_ksi: dict[str, str] = {
        clf["ksi_id"]: clf["status"] for clf in current.get("ksi_classifications", [])
    }

    entries: list[KsiDiffEntry] = []
    all_ksis = sorted(set(prior_by_ksi) | set(current_by_ksi))
    for ksi in all_ksis:
        in_prior = ksi in prior_by_ksi
        in_current = ksi in current_by_ksi
        prior_status = prior_by_ksi.get(ksi)
        current_status = current_by_ksi.get(ksi)

        if in_current and not in_prior:
            outcome: GapDiffOutcome = "added"
            movement = None
        elif in_prior and not in_current:
            outcome = "removed"
            movement = None
        elif prior_status == current_status:
            outcome = "unchanged"
            movement = None
        else:
            outcome = "status_changed"
            movement = _movement_label(prior_status, current_status)

        entries.append(
            KsiDiffEntry(
                ksi_id=ksi,
                outcome=outcome,
                prior_status=prior_status,
                current_status=current_status,
                severity_movement=movement,
            )
        )

    return GapDiff(
        prior_generated_at=prior.get("generated_at"),
        current_generated_at=current.get("generated_at"),
        prior_baseline_id=prior.get("baseline_id"),
        current_baseline_id=current.get("baseline_id"),
        entries=entries,
    )


def _movement_label(
    prior_status: str | None, current_status: str | None
) -> Literal["improved", "regressed", "shifted"]:
    """Classify a status change as improved / regressed / shifted.

    Improved: rank goes up (toward implemented or "moot" buckets).
    Regressed: rank goes down (toward not_implemented).
    Shifted: same rank but different label, OR the rank couldn't be
    resolved (unknown status string from a schema-newer report).
    """
    pr = _SEVERITY_RANK.get(prior_status or "", -1)
    cr = _SEVERITY_RANK.get(current_status or "", -1)
    if pr == -1 or cr == -1:
        return "shifted"
    if cr > pr:
        return "improved"
    if cr < pr:
        return "regressed"
    return "shifted"


def _validate_input(d: dict[str, Any], label: str) -> None:
    """Reject inputs that aren't gap-report sidecars."""
    if not isinstance(d, dict):
        raise ValueError(f"{label}: expected dict, got {type(d).__name__}")
    rt = d.get("report_type")
    if rt is not None and rt != "gap":
        raise ValueError(f"{label}: report_type={rt!r}, expected 'gap'")


# --- HTML rendering --------------------------------------------------------

_DIFF_BODY_TEMPLATE = """
<p class="meta">
  Comparing <strong>prior</strong> ({{ prior_generated_at or "unknown time" }})
  vs <strong>current</strong> ({{ current_generated_at or "unknown time" }}).
  Baselines:
  <code>{{ prior_baseline_id or "(unknown)" }}</code>
  vs
  <code>{{ current_baseline_id or "(unknown)" }}</code>.
</p>

<div class="diff-summary">
  <span class="diff-pill diff-added">{{ added | length }} added</span>
  <span class="diff-pill diff-removed">{{ removed | length }} removed</span>
  <span class="diff-pill diff-improved">{{ improved | length }} improved</span>
  <span class="diff-pill diff-regressed">{{ regressed | length }} regressed</span>
  <span class="diff-pill diff-shifted">{{ shifted | length }} shifted</span>
  <span class="diff-pill diff-unchanged">{{ unchanged | length }} unchanged</span>
</div>

{% if regressed %}
<h2 class="diff-section diff-regressed-h">Regressed ({{ regressed | length }})</h2>
<table>
  <thead><tr><th>KSI</th><th>Was</th><th>Now</th></tr></thead>
  <tbody>
    {% for e in regressed %}
    <tr>
      <td><span class="ksi-id">{{ e.ksi_id }}</span></td>
      <td><span class="status-pill status-{{ e.prior_status }}"
            >{{ e.prior_status | replace('_', ' ') }}</span></td>
      <td><span class="status-pill status-{{ e.current_status }}"
            >{{ e.current_status | replace('_', ' ') }}</span></td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

{% if added %}
<h2 class="diff-section diff-added-h">Added ({{ added | length }})</h2>
<table>
  <thead><tr><th>KSI</th><th>Status</th></tr></thead>
  <tbody>
    {% for e in added %}
    <tr>
      <td><span class="ksi-id">{{ e.ksi_id }}</span></td>
      <td><span class="status-pill status-{{ e.current_status }}"
            >{{ e.current_status | replace('_', ' ') }}</span></td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

{% if improved %}
<h2 class="diff-section diff-improved-h">Improved ({{ improved | length }})</h2>
<table>
  <thead><tr><th>KSI</th><th>Was</th><th>Now</th></tr></thead>
  <tbody>
    {% for e in improved %}
    <tr>
      <td><span class="ksi-id">{{ e.ksi_id }}</span></td>
      <td><span class="status-pill status-{{ e.prior_status }}"
            >{{ e.prior_status | replace('_', ' ') }}</span></td>
      <td><span class="status-pill status-{{ e.current_status }}"
            >{{ e.current_status | replace('_', ' ') }}</span></td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

{% if shifted %}
<h2 class="diff-section">Shifted ({{ shifted | length }})</h2>
<table>
  <thead><tr><th>KSI</th><th>Was</th><th>Now</th></tr></thead>
  <tbody>
    {% for e in shifted %}
    <tr>
      <td><span class="ksi-id">{{ e.ksi_id }}</span></td>
      <td><span class="status-pill status-{{ e.prior_status }}"
            >{{ (e.prior_status or "?") | replace('_', ' ') }}</span></td>
      <td><span class="status-pill status-{{ e.current_status }}"
            >{{ (e.current_status or "?") | replace('_', ' ') }}</span></td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

{% if removed %}
<h2 class="diff-section diff-removed-h">Removed ({{ removed | length }})</h2>
<table>
  <thead><tr><th>KSI</th><th>Was</th></tr></thead>
  <tbody>
    {% for e in removed %}
    <tr>
      <td><span class="ksi-id">{{ e.ksi_id }}</span></td>
      <td><span class="status-pill status-{{ e.prior_status }}"
            >{{ e.prior_status | replace('_', ' ') }}</span></td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

{% if unchanged %}
<details class="unchanged-collapsed">
  <summary>Unchanged ({{ unchanged | length }})</summary>
  <table>
    <thead><tr><th>KSI</th><th>Status</th></tr></thead>
    <tbody>
      {% for e in unchanged %}
      <tr>
        <td><span class="ksi-id">{{ e.ksi_id }}</span></td>
        <td><span class="status-pill status-{{ e.current_status }}"
              >{{ e.current_status | replace('_', ' ') }}</span></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</details>
{% endif %}
"""

_DIFF_CSS = """
<style>
  .diff-summary {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin: 12px 0 24px 0;
  }
  .diff-pill {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 14px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-transform: uppercase;
  }
  .diff-pill.diff-added     { background: #d1f4da; color: #0a4a17; }
  .diff-pill.diff-removed   { background: #f0e0e0; color: #5a3a3a; }
  .diff-pill.diff-improved  { background: #d6e5fa; color: #0a3a7a; }
  .diff-pill.diff-regressed { background: #fddede; color: #7a1f1f; }
  .diff-pill.diff-shifted   { background: #fff2c2; color: #6a4e00; }
  .diff-pill.diff-unchanged { background: #eaeef2; color: #444c56; }
  h2.diff-section.diff-regressed-h { color: #7a1f1f; }
  h2.diff-section.diff-improved-h  { color: #0a3a7a; }
  h2.diff-section.diff-added-h     { color: #0a4a17; }
  h2.diff-section.diff-removed-h   { color: #5a3a3a; }
  details.unchanged-collapsed { margin-top: 24px; }
  details.unchanged-collapsed > summary {
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    color: #4a4a4a;
    padding: 8px 0;
  }
  details.unchanged-collapsed > summary:hover { color: #0a2540; }
</style>
"""


def render_gap_diff_html(
    diff: GapDiff,
    *,
    generated_at: datetime | None = None,
) -> str:
    """Return a complete HTML document rendering of a GapDiff.

    Layout: top summary pills (added/removed/improved/regressed/shifted/
    unchanged counts), then per-category sections sorted by reviewer
    priority — Regressed first (action items), then Added, Improved,
    Shifted, Removed, and Unchanged collapsed under a `<details>`.
    """
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(_DIFF_BODY_TEMPLATE)

    shifted = [e for e in diff.entries if e.severity_movement == "shifted"]

    body = template.render(
        added=diff.added,
        removed=diff.removed,
        improved=diff.improved,
        regressed=diff.regressed,
        shifted=shifted,
        unchanged=diff.unchanged,
        prior_generated_at=diff.prior_generated_at,
        current_generated_at=diff.current_generated_at,
        prior_baseline_id=diff.prior_baseline_id,
        current_baseline_id=diff.current_baseline_id,
    )

    when = (generated_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    return render_base_document(
        title="Gap Diff",
        subtitle=(
            f"{len(diff.regressed)} regressed, "
            f"{len(diff.improved)} improved, "
            f"{len(diff.added)} added, "
            f"{len(diff.removed)} removed"
        ),
        body_html=_DIFF_CSS + body,
        generated_at=when,
    )
