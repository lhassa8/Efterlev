"""HTML rendering tests for `RemediationProposal`.

Same pattern as gap/documentation renderers: typed input → string output,
structural assertions only. What we check:
  - Document shell (doctype, title including KSI id, inline stylesheet).
  - The proposal card carries `.claim` class + DRAFT banner (diffs are
    Claims — the agent drafts, a human applies).
  - Status pills reflect proposed / no_terraform_fix.
  - Diff is rendered in a `<pre>` block (preserves whitespace).
  - Empty-diff case shows the "procedural gap" placeholder, NOT an empty
    <pre> block.
  - Cited evidence IDs + source file paths appear in output.
  - Claim record id surfaces for provenance walks.
  - XSS defense on explanation + diff content.
  - "How to apply" guidance is always present regardless of status.
"""

from __future__ import annotations

from datetime import UTC, datetime

from efterlev.agents import RemediationProposal
from efterlev.reports import render_remediation_proposal_html


def _proposal(
    *,
    ksi_id: str = "KSI-SVC-SNT",
    status: str = "proposed",
    diff: str = "--- a/main.tf\n+++ b/main.tf\n@@ -1 +1,2 @@\n x\n+y\n",
    explanation: str = "Add an HTTPS redirect to the HTTP listener.",
    cited_evidence_ids: list[str] | None = None,
    cited_source_files: list[str] | None = None,
    claim_record_id: str | None = "sha256:rec1",
) -> RemediationProposal:
    return RemediationProposal(
        ksi_id=ksi_id,
        status=status,  # type: ignore[arg-type]
        diff=diff,
        explanation=explanation,
        cited_evidence_ids=cited_evidence_ids or ["sha256:abc123"],
        cited_source_files=cited_source_files or ["infra/terraform/loadbalancer.tf"],
        claim_record_id=claim_record_id,
    )


def _when() -> datetime:
    return datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC)


def test_renders_complete_html_document() -> None:
    html = render_remediation_proposal_html(_proposal(), generated_at=_when())
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "<title>Remediation Proposal — KSI-SVC-SNT — Efterlev</title>" in html
    assert "<style>" in html


def test_proposal_card_is_a_claim_with_draft_banner() -> None:
    html = render_remediation_proposal_html(_proposal(), generated_at=_when())
    # Diffs are LLM-drafted. They must render as Claims with the DRAFT banner
    # per CLAUDE.md trust-class discipline.
    assert 'class="record claim"' in html
    assert "DRAFT" in html
    assert "requires human review" in html


def test_status_pill_reflects_proposed_status() -> None:
    html = render_remediation_proposal_html(_proposal(status="proposed"), generated_at=_when())
    assert "remediation-proposed" in html


def test_status_pill_reflects_no_terraform_fix_status() -> None:
    html = render_remediation_proposal_html(
        _proposal(status="no_terraform_fix", diff=""),
        generated_at=_when(),
    )
    assert "remediation-no_terraform_fix" in html


def test_diff_renders_in_pre_block() -> None:
    diff = "--- a/main.tf\n+++ b/main.tf\n@@ -1,3 +1,5 @@\n x\n+y\n z\n"
    html = render_remediation_proposal_html(_proposal(diff=diff), generated_at=_when())
    # `<pre class="diff">` keeps leading whitespace intact so `--- a/`, `+++ b/`,
    # and `@@` context headers land correctly.
    assert '<pre class="diff">' in html
    # Escaped markers appear in the output — we don't parse the diff,
    # just preserve it verbatim (Jinja autoescape handles `<`/`>`).
    assert "main.tf" in html
    assert "@@ -1,3 +1,5 @@" in html


def test_empty_diff_shows_procedural_placeholder_not_empty_pre() -> None:
    html = render_remediation_proposal_html(
        _proposal(
            status="no_terraform_fix",
            diff="",
            explanation="This gap is procedural.",
        ),
        generated_at=_when(),
    )
    assert "No Terraform remediation proposed" in html
    # Crucially: no `<pre class="diff">` block when diff is empty.
    assert '<pre class="diff">' not in html


def test_cited_evidence_ids_appear() -> None:
    html = render_remediation_proposal_html(
        _proposal(
            cited_evidence_ids=[
                "sha256:0123456789abcdef" * 4,
                "sha256:fedcba9876543210" * 4,
            ]
        ),
        generated_at=_when(),
    )
    assert "sha256:0123456789abcdef" in html
    assert "sha256:fedcba9876543210" in html


def test_cited_source_files_appear() -> None:
    html = render_remediation_proposal_html(
        _proposal(
            cited_source_files=[
                "infra/terraform/loadbalancer.tf",
                "infra/terraform/modules/tls/main.tf",
            ]
        ),
        generated_at=_when(),
    )
    assert "infra/terraform/loadbalancer.tf" in html
    assert "infra/terraform/modules/tls/main.tf" in html


def test_claim_record_id_surfaces_for_provenance_walk() -> None:
    html = render_remediation_proposal_html(
        _proposal(claim_record_id="sha256:recABCDEF"),
        generated_at=_when(),
    )
    assert "sha256:recABCDEF" in html


def test_explanation_escapes_raw_html() -> None:
    # A misbehaving LLM could put HTML in the explanation. Escape, don't inject.
    html = render_remediation_proposal_html(
        _proposal(explanation="<script>alert('xss')</script> bad prose"),
        generated_at=_when(),
    )
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html


def test_diff_escapes_raw_html() -> None:
    # Diffs can contain `<script>` literals inside the .tf source they diff.
    # Must be HTML-escaped inside the <pre> block, not injected.
    diff_with_html = (
        "--- a/tags.tf\n+++ b/tags.tf\n"
        '@@ -1 +1 @@\n-description = "<script>"\n+description = "fixed"\n'
    )
    html = render_remediation_proposal_html(_proposal(diff=diff_with_html), generated_at=_when())
    # Raw tag must not appear as live markup.
    assert '"<script>"' not in html
    # Escaped form IS present.
    assert "&lt;script&gt;" in html


def test_how_to_apply_guidance_always_present() -> None:
    # Guidance steps are static, always rendered, regardless of diff presence.
    # Gives a 3PAO / reviewer immediate next actions.
    for status, diff in [("proposed", "x"), ("no_terraform_fix", "")]:
        html = render_remediation_proposal_html(
            _proposal(status=status, diff=diff),
            generated_at=_when(),
        )
        assert "How to apply" in html
        assert "git apply --check" in html
        assert "efterlev scan" in html  # re-scan step reference


def test_manifest_cited_evidence_gets_attestation_badge() -> None:
    """When `evidence=` is passed, cited evidence records whose detector_id
    is "manifest" render with an attestation badge (fix for review finding 6).
    """
    from pathlib import Path

    from efterlev.models import Evidence, SourceRef

    detector_ev = Evidence.create(
        detector_id="aws.tls_on_lb_listeners",
        source_ref=SourceRef(file=Path("infra/lb.tf"), line_start=10, line_end=22),
        ksis_evidenced=["KSI-SVC-SNT"],
        controls_evidenced=["SC-8"],
        content={"resource_name": "public"},
        timestamp=_when(),
    )
    manifest_ev = Evidence.create(
        detector_id="manifest",
        source_ref=SourceRef(file=Path(".efterlev/manifests/inbox.yml")),
        ksis_evidenced=["KSI-AFR-FSI"],
        controls_evidenced=["IR-6"],
        content={"statement": "soc monitored"},
        timestamp=_when(),
    )
    html = render_remediation_proposal_html(
        _proposal(cited_evidence_ids=[detector_ev.evidence_id, manifest_ev.evidence_id]),
        evidence=[detector_ev, manifest_ev],
        generated_at=_when(),
    )
    assert ">attestation</span>" in html
    assert html.count("source-manifest") == 2  # CSS rule + one badge instance


def test_cited_evidence_without_evidence_kwarg_renders_unbadged() -> None:
    """Back-compat: callers not passing `evidence=` still get a valid
    report; citations render without badges."""
    html = render_remediation_proposal_html(_proposal(), generated_at=_when())
    assert "sha256:abc123" in html
    assert ">attestation</span>" not in html
