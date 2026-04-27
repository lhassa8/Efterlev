"""HTML rendering tests for Gap Report output.

Renderers are pure-function (typed-in → string-out), so tests construct
typed `GapReport` inputs directly and assert on structural properties
of the rendered HTML — not byte-identical snapshots, which would be
brittle against harmless stylesheet tweaks.

What we check:
  - Document shell (doctype, title, embedded stylesheet).
  - Evidence/Claims visual distinction per CLAUDE.md's trust-class rule:
    classification cards carry the `.claim` class + DRAFT banner.
  - Status-pill CSS classes match the classification's status.
  - Every cited evidence id appears in the rendered output so the user
    can cross-reference to `provenance show`.
  - XSS-adjacent inputs (evidence ids / rationales containing HTML) are
    escaped, not injected.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from efterlev.agents import GapReport
from efterlev.agents.gap import KsiClassification, UnmappedFinding
from efterlev.reports import render_gap_report_html

# --- KsiClassification model invariants ----------------------------------------


def test_implemented_classification_with_no_evidence_ids_is_rejected() -> None:
    """Defense-in-depth alongside the fence-citation validator.

    The fence validator (`_validate_cited_ids`) catches IDs the model
    fabricated against the prompt's nonced fences — but it never fires
    on zero citations because there's nothing to validate against. A
    model that returns status="implemented" with evidence_ids=[] is
    making an unfounded positive claim; reject at the model layer.
    """
    with pytest.raises(ValidationError, match="requires at least one evidence_id"):
        KsiClassification(
            ksi_id="KSI-SVC-SNT", status="implemented", rationale="ok", evidence_ids=[]
        )


def test_partial_classification_with_no_evidence_ids_is_rejected() -> None:
    with pytest.raises(ValidationError, match="requires at least one evidence_id"):
        KsiClassification(ksi_id="KSI-IAM-MFA", status="partial", rationale="ok", evidence_ids=[])


def test_not_implemented_classification_may_have_no_evidence_ids() -> None:
    """`not_implemented` is exempt — it's an honest declaration that the
    evidence is missing. Forcing citations would push the model to
    fabricate them.
    """
    clf = KsiClassification(
        ksi_id="KSI-MLA-LET", status="not_implemented", rationale="no evidence", evidence_ids=[]
    )
    assert clf.evidence_ids == []


def test_not_applicable_classification_may_have_no_evidence_ids() -> None:
    clf = KsiClassification(
        ksi_id="KSI-IAM-USR", status="not_applicable", rationale="out of scope", evidence_ids=[]
    )
    assert clf.evidence_ids == []


def test_evidence_layer_inapplicable_classification_may_have_no_evidence_ids() -> None:
    """SPEC-57.1: the new status is exempt from the citation requirement,
    same as not_implemented / not_applicable. The status itself is the
    declaration that the scanner has no path to evidence this KSI.
    """
    clf = KsiClassification(
        ksi_id="KSI-AFR-FSI",
        status="evidence_layer_inapplicable",
        rationale="FedRAMP Security Inbox is a procedural commitment with no IaC surface.",
        evidence_ids=[],
    )
    assert clf.status == "evidence_layer_inapplicable"
    assert clf.evidence_ids == []


def test_evidence_layer_inapplicable_renders_with_dedicated_status_pill() -> None:
    """SPEC-57.1: the new status gets its own CSS class so a reviewer can
    distinguish "scanner-coverage gap" from "real not_implemented finding"
    at a glance.
    """
    clf = KsiClassification(
        ksi_id="KSI-AFR-FSI",
        status="evidence_layer_inapplicable",
        rationale="ok",
        evidence_ids=[],
    )
    html = render_gap_report_html(_report(classifications=[clf]), **_baseline_kwargs())
    # The classification's status-pill CSS class names the new status.
    assert 'class="status-pill status-evidence_layer_inapplicable"' in html
    # The CSS rule for the new pill exists in the embedded stylesheet.
    assert ".status-evidence_layer_inapplicable" in html


# --- HTML rendering ------------------------------------------------------------


def _report(
    *,
    classifications: list[KsiClassification] | None = None,
    unmapped: list[UnmappedFinding] | None = None,
    claim_record_ids: list[str] | None = None,
) -> GapReport:
    return GapReport(
        ksi_classifications=classifications or [],
        unmapped_findings=unmapped or [],
        claim_record_ids=claim_record_ids or [],
    )


def _baseline_kwargs() -> dict:
    return {
        "baseline_id": "fedramp-20x-moderate",
        "frmr_version": "0.9.43-beta",
        "generated_at": datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC),
    }


def test_renders_complete_html_document() -> None:
    html = render_gap_report_html(_report(), **_baseline_kwargs())
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "<title>Gap Report — Efterlev</title>" in html
    # Stylesheet must be inlined — we promise portable self-contained HTML.
    assert "<style>" in html
    assert "</style>" in html


def test_classification_cards_carry_claim_class_and_draft_banner() -> None:
    clf = KsiClassification(
        ksi_id="KSI-SVC-SNT",
        status="partial",
        rationale="TLS on HTTPS listener; HTTP listener coexists without redirect.",
        evidence_ids=["sha256:abc"],
    )
    html = render_gap_report_html(_report(classifications=[clf]), **_baseline_kwargs())
    # CLAUDE.md: classifications are LLM-reasoned and must render as Claims,
    # not Evidence. The .claim CSS class + DRAFT banner enforce that visually.
    assert 'class="record claim"' in html
    assert "DRAFT" in html
    assert "requires human review" in html


def test_status_pill_classes_reflect_classification_status() -> None:
    # Positive statuses require at least one evidence_id citation per the
    # KsiClassification model invariant (gap.py 2026-04-25). The
    # placeholder hash is ignored by render_gap_report_html — this test
    # only cares about the status pill CSS classes.
    placeholder = "sha256:" + "0" * 64
    classifications = [
        KsiClassification(
            ksi_id="KSI-SVC-SNT",
            status="implemented",
            rationale="ok",
            evidence_ids=[placeholder],
        ),
        KsiClassification(
            ksi_id="KSI-IAM-MFA",
            status="partial",
            rationale="ok",
            evidence_ids=[placeholder],
        ),
        KsiClassification(
            ksi_id="KSI-MLA-LET",
            status="not_implemented",
            rationale="ok",
            evidence_ids=[],
        ),
    ]
    html = render_gap_report_html(_report(classifications=classifications), **_baseline_kwargs())
    assert "status-implemented" in html
    assert "status-partial" in html
    assert "status-not_implemented" in html


def test_cited_evidence_ids_appear_in_output() -> None:
    clf = KsiClassification(
        ksi_id="KSI-SVC-SNT",
        status="partial",
        rationale="x",
        evidence_ids=[
            "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
        ],
    )
    html = render_gap_report_html(_report(classifications=[clf]), **_baseline_kwargs())
    for eid in clf.evidence_ids:
        assert eid in html


def test_claim_record_ids_section_renders() -> None:
    html = render_gap_report_html(
        _report(claim_record_ids=["sha256:rec1", "sha256:rec2"]),
        **_baseline_kwargs(),
    )
    assert "Provenance record IDs" in html
    assert "sha256:rec1" in html
    assert "sha256:rec2" in html
    assert "efterlev provenance show" in html


def test_unmapped_findings_render_in_own_section() -> None:
    finding = UnmappedFinding(
        evidence_id="sha256:abcdef",
        controls=["SC-28", "SC-28(1)"],
        note="S3 bucket logs has AES256 at rest; no FRMR KSI currently maps here.",
    )
    html = render_gap_report_html(_report(unmapped=[finding]), **_baseline_kwargs())
    assert "Unmapped findings" in html
    assert "SC-28" in html
    # Unmapped findings are deterministic scanner output — render as Evidence, not Claim.
    assert 'class="record evidence"' in html


def test_html_escapes_html_in_rationale() -> None:
    # A misbehaving LLM could return a rationale containing HTML. Must be escaped,
    # not inserted as live markup — users open these reports in browsers.
    clf = KsiClassification(
        ksi_id="KSI-SVC-SNT",
        status="partial",
        rationale="<script>alert('xss')</script> malicious",
        evidence_ids=["sha256:" + "0" * 64],
    )
    html = render_gap_report_html(_report(classifications=[clf]), **_baseline_kwargs())
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html


def test_html_escapes_html_in_baseline_metadata() -> None:
    # Defense-in-depth: the baseline_id / frmr_version metadata is also escaped
    # by the document shell. A repo shipping a hostile frmr_version string
    # shouldn't render as live markup.
    html = render_gap_report_html(
        _report(),
        baseline_id="<img src=x>",
        frmr_version="0.9.43-beta",
        generated_at=datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC),
    )
    assert "<img src=x>" not in html
    assert "&lt;img" in html


def test_empty_report_still_renders_valid_document() -> None:
    # No classifications, no unmapped findings — the report should still be
    # a valid document (not a traceback, not an empty string).
    html = render_gap_report_html(_report(), **_baseline_kwargs())
    assert "<!DOCTYPE html>" in html
    assert "0 KSI classification(s), 0 unmapped finding(s)" in html


def test_manifest_cited_evidence_gets_attestation_badge() -> None:
    """When `evidence=` is passed, manifest-sourced citations render with a
    badge so a 3PAO or reviewer can tell human-signed evidence from
    scanner-derived evidence at a glance. Fix for review finding 5.
    """
    from pathlib import Path

    from efterlev.models import Evidence, SourceRef

    detector_ev = Evidence.create(
        detector_id="aws.encryption_s3_at_rest",
        source_ref=SourceRef(file=Path("main.tf"), line_start=1, line_end=10),
        ksis_evidenced=["KSI-SVC-VRI"],
        controls_evidenced=["SC-28"],
        content={"resource_name": "audit"},
        timestamp=datetime(2026, 4, 22, tzinfo=UTC),
    )
    manifest_ev = Evidence.create(
        detector_id="manifest",
        source_ref=SourceRef(file=Path(".efterlev/manifests/security-inbox.yml")),
        ksis_evidenced=["KSI-AFR-FSI"],
        controls_evidenced=["IR-6"],
        content={"statement": "soc monitored 24/7"},
        timestamp=datetime(2026, 4, 22, tzinfo=UTC),
    )
    clf = KsiClassification(
        ksi_id="KSI-AFR-FSI",
        status="implemented",
        rationale="Human-attested procedural coverage in manifest.",
        evidence_ids=[detector_ev.evidence_id, manifest_ev.evidence_id],
    )
    html = render_gap_report_html(
        _report(classifications=[clf]),
        evidence=[detector_ev, manifest_ev],
        **_baseline_kwargs(),
    )
    # Two citations rendered; exactly one badge (the manifest-sourced one).
    assert detector_ev.evidence_id in html
    assert manifest_ev.evidence_id in html
    assert ">attestation</span>" in html
    # One source-manifest CSS rule + exactly one badge instance = 2 occurrences.
    assert html.count("source-manifest") == 2


def test_citations_without_evidence_kwarg_render_unbadged() -> None:
    """Pre-existing callers that don't pass `evidence=` still work: citations
    render without any badge (detector-source default)."""
    clf = KsiClassification(
        ksi_id="KSI-SVC-VRI",
        status="partial",
        rationale="ok",
        evidence_ids=["sha256:abc"],
    )
    html = render_gap_report_html(_report(classifications=[clf]), **_baseline_kwargs())
    assert "sha256:abc" in html
    # Stylesheet still defines `.source-manifest`; no badge element should fire.
    assert ">attestation</span>" not in html


# --- boundary scoping rendering (Priority 4.2, 2026-04-27) ----------------


def _ev(
    *,
    boundary_state: str = "boundary_undeclared",
    detector_id: str = "aws.encryption_s3_at_rest",
    resource_name: str = "logs",
):
    """Test helper that constructs an Evidence with an explicit boundary_state."""
    from pathlib import Path

    from efterlev.models import Evidence, SourceRef

    return Evidence.create(
        detector_id=detector_id,
        source_ref=SourceRef(file=Path("infra/main.tf"), line_start=1, line_end=10),
        ksis_evidenced=["KSI-SVC-VRI"],
        controls_evidenced=["SC-28"],
        content={"resource_name": resource_name, "encryption_state": "present"},
        timestamp=datetime(2026, 4, 27, tzinfo=UTC),
        boundary_state=boundary_state,  # type: ignore[arg-type]
    )


def test_undeclared_workspace_renders_boundary_banner() -> None:
    """When every Evidence is `boundary_undeclared`, the report includes the
    top-of-report banner directing the customer to declare scope."""
    ev = _ev(boundary_state="boundary_undeclared")
    clf = KsiClassification(
        ksi_id="KSI-SVC-VRI", status="partial", rationale="ok", evidence_ids=[ev.evidence_id]
    )
    html = render_gap_report_html(
        _report(classifications=[clf]), evidence=[ev], **_baseline_kwargs()
    )
    assert "boundary-banner" in html
    assert "FedRAMP boundary not declared" in html
    assert "efterlev boundary set" in html


def test_declared_workspace_omits_boundary_banner() -> None:
    """When ANY Evidence has a real boundary classification, the workspace has
    a declaration and the banner doesn't render."""
    ev = _ev(boundary_state="in_boundary")
    clf = KsiClassification(
        ksi_id="KSI-SVC-VRI", status="partial", rationale="ok", evidence_ids=[ev.evidence_id]
    )
    html = render_gap_report_html(
        _report(classifications=[clf]), evidence=[ev], **_baseline_kwargs()
    )
    # The CSS class definition stays in the stylesheet (other reports may use it);
    # what we assert is that no rendered <div> in the body uses the banner classes.
    assert '<div class="boundary-banner' not in html
    assert "FedRAMP boundary not declared" not in html


def test_in_boundary_classification_renders_in_boundary_pill() -> None:
    """A classification whose cited evidence is `in_boundary` gets a badge."""
    ev = _ev(boundary_state="in_boundary")
    clf = KsiClassification(
        ksi_id="KSI-SVC-VRI", status="partial", rationale="ok", evidence_ids=[ev.evidence_id]
    )
    html = render_gap_report_html(
        _report(classifications=[clf]), evidence=[ev], **_baseline_kwargs()
    )
    assert "boundary-in_boundary" in html
    # Not a collapsed details — in-boundary findings stay visible. The CSS
    # stylesheet contains the class definition (and the word `<details>` in
    # one of its comments); the assertion targets actual HTML element usage.
    assert "<details class=" not in html


def test_out_of_boundary_classification_collapses_under_details() -> None:
    """A classification whose cited evidence is entirely out_of_boundary
    renders inside a `<details>` element so reviewers focus on in-scope
    findings while still being able to expand and inspect."""
    ev = _ev(boundary_state="out_of_boundary")
    clf = KsiClassification(
        ksi_id="KSI-SVC-VRI",
        status="not_implemented",
        rationale="something",
        evidence_ids=[ev.evidence_id],
    )
    html = render_gap_report_html(
        _report(classifications=[clf]), evidence=[ev], **_baseline_kwargs()
    )
    assert "out-of-boundary-collapsed" in html
    assert "<details" in html
    assert "boundary-out_of_boundary" in html
    # The "click to expand" hint is part of the collapsed UX.
    assert "click to expand" in html


def test_mixed_boundary_classification_resolves_to_in_boundary() -> None:
    """When a classification cites both in-boundary and out-of-boundary evidence,
    the in-boundary one wins — the finding is worth surfacing."""
    in_ev = _ev(boundary_state="in_boundary", resource_name="prod_logs")
    out_ev = _ev(boundary_state="out_of_boundary", resource_name="staging_logs")
    clf = KsiClassification(
        ksi_id="KSI-SVC-VRI",
        status="partial",
        rationale="ok",
        evidence_ids=[in_ev.evidence_id, out_ev.evidence_id],
    )
    html = render_gap_report_html(
        _report(classifications=[clf]), evidence=[in_ev, out_ev], **_baseline_kwargs()
    )
    assert "<details class=" not in html
    assert "boundary-in_boundary" in html
