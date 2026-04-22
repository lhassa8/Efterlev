"""HTML rendering tests for Documentation Report output.

Same pattern as test_gap_report_html: typed input → string output,
structural assertions only (no byte-identical snapshots).

What we check:
  - Document shell (doctype, title, inline stylesheet).
  - Every attestation card carries `.claim` class + DRAFT banner
    (narratives are LLM-authored, must render as Claims per CLAUDE.md).
  - Status pills color-code according to classification status.
  - Cited evidence IDs + source file refs appear in output.
  - Narrative text is escaped (XSS defense).
  - Skipped-KSIs section renders when populated.
  - Empty report still renders a valid document.
  - Paragraph breaks in narrative text are visually preserved.
"""

from __future__ import annotations

from datetime import UTC, datetime

from efterlev.agents import DocumentationReport, KsiAttestation
from efterlev.models import AttestationCitation, AttestationDraft
from efterlev.reports import render_documentation_report_html


def _draft(
    *,
    ksi_id: str = "KSI-SVC-SNT",
    status: str | None = "partial",
    narrative: str | None = "TLS is configured on the main listener.",
    citations: list[AttestationCitation] | None = None,
) -> AttestationDraft:
    return AttestationDraft(
        ksi_id=ksi_id,
        baseline_id="fedramp-20x-moderate",
        frmr_version="0.9.43-beta",
        mode="agent_drafted",
        citations=citations or [],
        status=status,  # type: ignore[arg-type]
        narrative=narrative,
    )


def _report(
    *,
    attestations: list[KsiAttestation] | None = None,
    skipped: list[str] | None = None,
) -> DocumentationReport:
    return DocumentationReport(
        attestations=attestations or [],
        skipped_ksi_ids=skipped or [],
    )


def _kwargs() -> dict:
    return {
        "baseline_id": "fedramp-20x-moderate",
        "frmr_version": "0.9.43-beta",
        "generated_at": datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC),
    }


def test_renders_complete_html_document() -> None:
    html = render_documentation_report_html(_report(), **_kwargs())
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "<title>Documentation Report — Efterlev</title>" in html
    assert "<style>" in html


def test_attestation_cards_carry_claim_class_and_draft_banner() -> None:
    att = KsiAttestation(draft=_draft(), claim_record_id="sha256:rec1")
    html = render_documentation_report_html(_report(attestations=[att]), **_kwargs())
    # Narratives are LLM-authored. Per CLAUDE.md trust-class discipline,
    # they MUST render as Claims with the DRAFT banner.
    assert 'class="record claim"' in html
    assert "DRAFT" in html
    assert "requires human review" in html


def test_status_pills_reflect_classification_status() -> None:
    atts = [
        KsiAttestation(draft=_draft(ksi_id="KSI-A", status="implemented"), claim_record_id=None),
        KsiAttestation(draft=_draft(ksi_id="KSI-B", status="partial"), claim_record_id=None),
        KsiAttestation(
            draft=_draft(ksi_id="KSI-C", status="not_implemented"), claim_record_id=None
        ),
    ]
    html = render_documentation_report_html(_report(attestations=atts), **_kwargs())
    assert "status-implemented" in html
    assert "status-partial" in html
    assert "status-not_implemented" in html


def test_citations_render_with_source_file_and_detector_id() -> None:
    cite = AttestationCitation(
        evidence_id="sha256:abc123",
        detector_id="aws.tls_on_lb_listeners",
        source_file="infra/terraform/loadbalancer.tf",
        source_lines="42-58",
    )
    att = KsiAttestation(draft=_draft(citations=[cite]), claim_record_id=None)
    html = render_documentation_report_html(_report(attestations=[att]), **_kwargs())
    assert "sha256:abc123" in html
    assert "aws.tls_on_lb_listeners" in html
    assert "infra/terraform/loadbalancer.tf" in html
    assert "42-58" in html


def test_manifest_citation_carries_attestation_badge() -> None:
    # A citation with detector_id="manifest" (human-signed procedural
    # attestation) is visually distinguished in the rendered report so a
    # 3PAO or engineer scanning the doc can tell scanner-derived Evidence
    # from human-attested Evidence at a glance.
    manifest_cite = AttestationCitation(
        evidence_id="sha256:manifestAAA",
        detector_id="manifest",
        source_file=".efterlev/manifests/security-inbox.yml",
        source_lines=None,
    )
    detector_cite = AttestationCitation(
        evidence_id="sha256:detectorBBB",
        detector_id="aws.cloudtrail_audit_logging",
        source_file="infra/terraform/cloudtrail.tf",
        source_lines="10-24",
    )
    att = KsiAttestation(
        draft=_draft(citations=[manifest_cite, detector_cite]),
        claim_record_id=None,
    )
    html = render_documentation_report_html(_report(attestations=[att]), **_kwargs())
    # Manifest citation gets the badge; detector citation does not. A single
    # `source-manifest` class occurrence in the body proves the branch fires
    # once and only once across the two cited records.
    assert "source-manifest" in html
    assert html.count("source-manifest") == 2  # CSS rule + one badge instance
    assert ">attestation</span>" in html
    # Both evidence ids still render; the badge is additive, not replacing.
    assert "sha256:manifestAAA" in html
    assert "sha256:detectorBBB" in html


def test_claim_record_id_surfaces_for_provenance_walk() -> None:
    att = KsiAttestation(draft=_draft(), claim_record_id="sha256:recABC")
    html = render_documentation_report_html(_report(attestations=[att]), **_kwargs())
    assert "sha256:recABC" in html


def test_skipped_ksi_ids_section_renders() -> None:
    html = render_documentation_report_html(
        _report(skipped=["KSI-AFR-ADS", "KSI-CNA-DFP"]),
        **_kwargs(),
    )
    assert "Skipped KSIs" in html
    assert "KSI-AFR-ADS" in html
    assert "KSI-CNA-DFP" in html


def test_html_escapes_narrative_markup() -> None:
    # A misbehaving LLM could return a narrative containing raw HTML.
    # Must be escaped — users open these reports in browsers.
    att = KsiAttestation(
        draft=_draft(narrative="<script>alert('xss')</script> malicious prose"),
        claim_record_id=None,
    )
    html = render_documentation_report_html(_report(attestations=[att]), **_kwargs())
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html


def test_empty_narrative_renders_scanner_only_placeholder() -> None:
    # Scanner-only skeletons (mode="scanner_only") have narrative=None.
    # The renderer shouldn't fail — it should show an explanatory placeholder.
    att = KsiAttestation(
        draft=AttestationDraft(
            ksi_id="KSI-SVC-SNT",
            baseline_id="fedramp-20x-moderate",
            frmr_version="0.9.43-beta",
            mode="scanner_only",
            citations=[],
            status=None,
            narrative=None,
        ),
        claim_record_id=None,
    )
    html = render_documentation_report_html(_report(attestations=[att]), **_kwargs())
    assert "scanner-only skeleton" in html


def test_empty_report_still_renders_valid_document() -> None:
    html = render_documentation_report_html(_report(), **_kwargs())
    assert "<!DOCTYPE html>" in html
    assert "0 attestation(s) drafted, 0 skipped" in html


def test_narrative_paragraph_breaks_preserved_via_pre_wrap() -> None:
    # Narratives span multiple paragraphs; the renderer uses
    # `white-space: pre-wrap` rather than manual <p> splitting.
    # The stylesheet rule must exist so browsers render the breaks.
    att = KsiAttestation(
        draft=_draft(narrative="Paragraph one.\n\nParagraph two."),
        claim_record_id=None,
    )
    html = render_documentation_report_html(_report(attestations=[att]), **_kwargs())
    assert "white-space: pre-wrap" in html
    assert "Paragraph one." in html
    assert "Paragraph two." in html
