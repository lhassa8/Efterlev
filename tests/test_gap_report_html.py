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

from efterlev.agents import GapReport
from efterlev.agents.gap import KsiClassification, UnmappedFinding
from efterlev.reports import render_gap_report_html


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
    classifications = [
        KsiClassification(
            ksi_id="KSI-SVC-SNT", status="implemented", rationale="ok", evidence_ids=[]
        ),
        KsiClassification(ksi_id="KSI-IAM-MFA", status="partial", rationale="ok", evidence_ids=[]),
        KsiClassification(
            ksi_id="KSI-MLA-LET", status="not_implemented", rationale="ok", evidence_ids=[]
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
        evidence_ids=[],
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
