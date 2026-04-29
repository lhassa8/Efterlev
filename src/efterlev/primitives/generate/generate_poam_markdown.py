"""`generate_poam_markdown` primitive — deterministic POA&M assembly.

A POA&M (Plan of Action and Milestones) is the FedRAMP artifact that
tracks open security findings, their remediation plans, milestones, and
target completion dates. `docs/icp.md` names it as a direct ICP need:
first-FedRAMP-Moderate SaaS companies must produce one for every
authorization package, and today they hand-write it in a spreadsheet.

This primitive takes a list of `KsiClassification` records (from a Gap
Agent run) plus the FRMR indicator catalog, and produces a markdown
POA&M suitable for:

  - paste into Jira / Linear (their markdown-paste flows accept tables
    and per-item sections cleanly),
  - handing to a 3PAO alongside the FRMR attestation JSON,
  - a developer's own pre-submission review pass.

**Deterministic: no LLM involvement.** Every field is either derived
from the classification/FRMR data or emitted as a clearly-marked DRAFT
placeholder the user is expected to fill in before submission.
Deterministic-only output means zero per-run LLM cost and no
re-run-produces-different-text concern.

**Open items only.** `implemented` and `not_applicable` classifications
produce no POA&M entries — by definition, those don't need remediation
plans. Every `partial` and `not_implemented` classification becomes
one POA&M item with:

  - `POA&M Item ID` = `POAM-<KSI-id>-<first-8-of-claim-id-or-index>`
  - `Weakness Description` from the KSI statement + classification status
  - `Severity` by heuristic: `not_implemented` → HIGH, `partial` → MEDIUM.
    A DRAFT note says "reviewer must confirm severity per internal risk
    framework" — the heuristic is a starting point, not a judgment.
  - `Controls` from FRMR: the 800-53 controls listed in the KSI's
    `controls` array.
  - `Evidence Cited` from the classification's `evidence_ids` (short
    sha256 prefixes).
  - `Finding Rationale` verbatim from the Gap Agent's classification.
  - `Remediation Plan` / `Milestones` / `Target Completion Date` /
    `Owner` / `POC Email` / `Risk Accepted` / `Residual Risk` — all
    DRAFT placeholders. These are the fields a 3PAO expects to be
    filled; the tool can't infer them from static analysis.

See DECISIONS 2026-04-23 "POA&M markdown output primitive" for the
design record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from efterlev.models import Indicator
from efterlev.primitives.base import primitive

# Only classifications in these two statuses produce POA&M entries.
_STATUS_IN_SCOPE = {"partial", "not_implemented"}

# Severity heuristic. Documented in the output markdown as reviewer-
# adjustable. Keeping this in one place makes it one-line-editable when
# the organization's risk framework settles.
_SEVERITY_FOR_STATUS = {
    "not_implemented": "HIGH",
    "partial": "MEDIUM",
}

# Severity rank for the default sort mode. Lower number = earlier in the
# POA&M. Items at the same rank fall back to alphabetical KSI ID for
# stability.
_SEVERITY_RANK = {
    "not_implemented": 0,
    "partial": 1,
}

_DRAFT_PLACEHOLDER = "DRAFT — SET BEFORE SUBMISSION"

PoamSortMode = Literal["severity", "csx-ord"]


class PoamClassificationInput(BaseModel):
    """Minimal shape needed from a KsiClassification to emit a POA&M row.

    Decoupled from `efterlev.agents.gap.KsiClassification` at the
    primitive boundary — the primitive doesn't depend on any agent
    module. Callers that have a `KsiClassification` construct one of
    these by picking fields; the loop lives in CLI.
    """

    model_config = ConfigDict(frozen=True)

    ksi_id: str
    status: str
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    claim_record_id: str | None = None


class GeneratePoamMarkdownInput(BaseModel):
    """Input to `generate_poam_markdown`."""

    model_config = ConfigDict(frozen=True)

    classifications: list[PoamClassificationInput]
    indicators: dict[str, Indicator]
    baseline_id: str
    frmr_version: str
    # Generated-at for the header. Frozen at construction to keep the
    # primitive deterministic — same inputs → same markdown.
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Sort mode for the POA&M items. "severity" (default): not_implemented
    # (HIGH) first, then partial (MEDIUM); within tier, alphabetical by
    # KSI ID. "csx-ord": items appear in the order their KSI ID matches
    # `csx_ord_sequence`; non-prescribed items follow alphabetically.
    # See KSI-CSX-ORD in the FRMR catalog for the prescribed sequence.
    sort_mode: PoamSortMode = "severity"
    # Prescribed KSI ID sequence from KSI-CSX-ORD's `following_information`.
    # Required when sort_mode="csx-ord"; ignored otherwise. Loaded by the
    # CLI from FrmrDocument.csx_ord_sequence.
    csx_ord_sequence: list[str] = Field(default_factory=list)


class GeneratePoamMarkdownOutput(BaseModel):
    """Output: POA&M markdown string + per-KSI item count."""

    model_config = ConfigDict(frozen=True)

    markdown: str
    item_count: int
    # KSIs skipped because the classification references an id that
    # isn't in the loaded indicator dict. Follows the same posture as
    # `generate_frmr_attestation` (DECISIONS 2026-04-22 Phase 2 design
    # call #4): skip + report, don't fabricate.
    skipped_unknown_ksi: list[str] = Field(default_factory=list)


@primitive(capability="generate", side_effects=False, version="0.1.0", deterministic=True)
def generate_poam_markdown(
    input: GeneratePoamMarkdownInput,
) -> GeneratePoamMarkdownOutput:
    """Emit a POA&M markdown document from Gap-Agent classifications.

    Deterministic: same inputs → byte-identical output. No LLM call.
    Every item in the rendered POA&M is a `partial` or `not_implemented`
    KSI; `implemented`, `not_applicable`, and `evidence_layer_inapplicable`
    classifications are skipped (the latter is SPEC-57.1's distinct
    "scanner has no path to evidence this KSI by design" status — it's a
    coverage statement, not a remediation item).

    Unknown-KSI classifications (KSI id not in `indicators`) are
    reported in `skipped_unknown_ksi` — never fabricated into a POA&M
    row. Same posture as `generate_frmr_attestation`.
    """
    open_items = [c for c in input.classifications if c.status in _STATUS_IN_SCOPE]
    open_items = _sort_items(open_items, input.sort_mode, input.csx_ord_sequence)

    skipped: list[str] = []
    rendered_items: list[str] = []
    seen_skipped: set[str] = set()

    for idx, clf in enumerate(open_items):
        ind = input.indicators.get(clf.ksi_id)
        if ind is None:
            if clf.ksi_id not in seen_skipped:
                skipped.append(clf.ksi_id)
                seen_skipped.add(clf.ksi_id)
            continue
        rendered_items.append(_render_item(clf, ind, idx))

    markdown = _render_document(
        items=rendered_items,
        item_count=len(rendered_items),
        baseline_id=input.baseline_id,
        frmr_version=input.frmr_version,
        generated_at=input.generated_at,
    )

    return GeneratePoamMarkdownOutput(
        markdown=markdown,
        item_count=len(rendered_items),
        skipped_unknown_ksi=skipped,
    )


def _sort_items(
    items: list[PoamClassificationInput],
    sort_mode: PoamSortMode,
    csx_ord_sequence: list[str],
) -> list[PoamClassificationInput]:
    """Order POA&M items by the requested mode.

    - "severity" (default): not_implemented (HIGH) first, then partial
      (MEDIUM); ties broken alphabetically by KSI ID. Prior to v0.1.x this
      mode preserved input order, which made the output non-deterministic
      across runs that had the same classification set in different order.
      Now items are sorted explicitly.
    - "csx-ord": items appear in the order prescribed by KSI-CSX-ORD's
      `following_information` (resolved to KSI IDs by the loader). Items
      whose KSI is not in the prescribed sequence appear after, ordered
      alphabetically by KSI ID. The prescribed sequence carries 10 KSIs
      (all in theme AFR); themes outside AFR will always sort to the
      tail under this mode.
    """
    if sort_mode == "csx-ord":
        # Build rank map: prescribed sequence first (rank 0..N-1), all
        # else after. Stable sort means items with the same rank keep
        # their relative order, which we then break alphabetically.
        rank = {ksi_id: i for i, ksi_id in enumerate(csx_ord_sequence)}
        tail_rank = len(csx_ord_sequence)
        return sorted(
            items,
            key=lambda c: (rank.get(c.ksi_id, tail_rank), c.ksi_id),
        )
    # severity mode (default)
    return sorted(
        items,
        key=lambda c: (_SEVERITY_RANK.get(c.status, 99), c.ksi_id),
    )


def _render_document(
    *,
    items: list[str],
    item_count: int,
    baseline_id: str,
    frmr_version: str,
    generated_at: datetime,
) -> str:
    """Assemble the full POA&M markdown: header + summary table + per-item details."""
    ts_iso = generated_at.isoformat()

    lines: list[str] = []
    lines.append(f"# POA&M — {baseline_id}")
    lines.append("")
    lines.append(
        "**DRAFT — requires human review.** This POA&M was generated from the "
        "Gap Agent's KSI classifications. Every field marked "
        f"`{_DRAFT_PLACEHOLDER}` must be completed by a qualified reviewer "
        "before submission to any authorizing body. Severity is a starting-"
        "point heuristic (not_implemented → HIGH, partial → MEDIUM); reviewer "
        "must confirm severity per the organization's risk framework."
    )
    lines.append("")
    lines.append(
        f"- **Baseline:** {baseline_id}  \n"
        f"- **FRMR version:** {frmr_version}  \n"
        f"- **Generated:** {ts_iso}  \n"
        f"- **Open items:** {item_count}"
    )
    lines.append("")

    if item_count == 0:
        lines.append(
            "_No open POA&M items._ Every classified KSI is `implemented` or "
            "`not_applicable`; no `partial` or `not_implemented` findings to track."
        )
        lines.append("")
        return "\n".join(lines)

    # Summary table — quickly skimmable.
    lines.append("## Summary")
    lines.append("")
    lines.append("| POA&M ID | KSI | Status | Severity |")
    lines.append("|---|---|---|---|")
    for item_block in items:
        # Each rendered item starts with `### POAM-... — KSI ...` ; extract
        # the summary row from the item's frontmatter block.
        summary_line = _extract_summary_row(item_block)
        lines.append(summary_line)
    lines.append("")

    lines.append("## Items")
    lines.append("")
    for item_block in items:
        lines.append(item_block)

    return "\n".join(lines)


def _render_item(clf: PoamClassificationInput, indicator: Indicator, idx: int) -> str:
    """Render one POA&M item as a self-contained markdown block."""
    poam_id = _item_id(clf, idx)
    severity = _SEVERITY_FOR_STATUS.get(clf.status, "TBD")
    controls_str = ", ".join(indicator.controls) if indicator.controls else "—"
    # Short sha256 prefix (first 14 chars after `sha256:`) keeps the table
    # readable; full IDs live in the detail section.
    evidence_prefixes = ", ".join(_short_id(e) for e in clf.evidence_ids[:5])
    if not evidence_prefixes:
        evidence_prefixes = "_(none — classification has no cited evidence)_"
    elif len(clf.evidence_ids) > 5:
        evidence_prefixes += f", … (+{len(clf.evidence_ids) - 5} more)"

    ksi_name = indicator.name or clf.ksi_id

    lines = [
        f"### {poam_id} — {clf.ksi_id}: {ksi_name}",
        "",
        # Frontmatter block — the summary-row extractor parses this.
        f"- **POA&M ID:** `{poam_id}`",
        f"- **KSI:** `{clf.ksi_id}` — {ksi_name}",
        f"- **Status:** `{clf.status}`",
        f"- **Severity (draft heuristic):** `{severity}`",
        f"- **800-53 Controls:** {controls_str}",
        f"- **Evidence cited:** {evidence_prefixes}",
        "",
        "#### KSI Statement (FRMR)",
        "",
        f"> {indicator.statement or '_(no statement in FRMR)_'}",
        "",
        "#### Finding Rationale (Gap Agent)",
        "",
        clf.rationale.strip() or "_(no rationale recorded)_",
        "",
        "#### Reviewer Fields — complete before submission",
        "",
        f"- **Weakness Title:** `{_DRAFT_PLACEHOLDER}` (e.g. short one-line summary)",
        f"- **Remediation Plan:** `{_DRAFT_PLACEHOLDER}`",
        f"- **Milestones:** `{_DRAFT_PLACEHOLDER}`",
        f"- **Target Completion Date:** `{_DRAFT_PLACEHOLDER}`",
        f"- **Owner:** `{_DRAFT_PLACEHOLDER}`",
        f"- **POC Email:** `{_DRAFT_PLACEHOLDER}`",
        f"- **Residual Risk Summary:** `{_DRAFT_PLACEHOLDER}`",
        f"- **Risk Accepted?:** `{_DRAFT_PLACEHOLDER}` (yes/no/conditional)",
        "",
    ]
    if clf.claim_record_id:
        lines.append(
            f"#### Provenance\n\n"
            f"Walk the full classification chain with "
            f"`efterlev provenance show {clf.claim_record_id}`."
        )
        lines.append("")
    # Full evidence id list (for completeness, since summary truncated at 5).
    if len(clf.evidence_ids) > 5:
        lines.append("#### Full evidence citations")
        lines.append("")
        for e in clf.evidence_ids:
            lines.append(f"- `{e}`")
        lines.append("")
    return "\n".join(lines)


def _item_id(clf: PoamClassificationInput, idx: int) -> str:
    """Stable POA&M item identifier.

    Prefer the Claim record_id prefix (gives the item a provenance-graph
    anchor); fall back to the positional index if the classification has
    no persisted claim (e.g. fresh in-memory run).
    """
    if clf.claim_record_id:
        return f"POAM-{clf.ksi_id}-{_short_id(clf.claim_record_id)}"
    return f"POAM-{clf.ksi_id}-{idx:03d}"


def _short_id(full_id: str) -> str:
    """Trim `sha256:abcdef...` to `abcdef12` for display."""
    if full_id.startswith("sha256:"):
        return full_id[len("sha256:") : len("sha256:") + 8]
    return full_id[:8]


def _extract_summary_row(item_block: str) -> str:
    """Pull one-line summary row from a rendered item block for the top table.

    The item block's frontmatter has the `POA&M ID`, `KSI`, `Status`,
    `Severity` bullets in a fixed order — parse those lines back out to
    produce `| id | ksi | status | severity |`.
    """
    poam_id = _grep_value(item_block, "**POA&M ID:**")
    ksi_bullet = _grep_value(item_block, "**KSI:**")
    status = _grep_value(item_block, "**Status:**")
    severity = _grep_value(item_block, "**Severity (draft heuristic):**")
    return f"| {poam_id} | {ksi_bullet} | {status} | {severity} |"


def _grep_value(block: str, label: str) -> str:
    """Find the bullet line `- <label> VALUE` and return VALUE. Returns '—' if absent."""
    for line in block.splitlines():
        if line.startswith(f"- {label}"):
            return line.split(label, 1)[1].strip()
    return "—"
