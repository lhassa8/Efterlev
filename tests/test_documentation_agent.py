"""Documentation Agent tests — narrative synthesis, composition, injection defense.

No network calls — every test injects `StubLLMClient`. Tests cover:
  - Happy path: LLM narrative → agent_drafted AttestationDraft persisted.
  - only_ksi filter.
  - not_applicable classifications are skipped.
  - Classification referencing a KSI not in the baseline is skipped.
  - Prompt-injection defense: fabricated evidence IDs → AgentError.
  - reconstruct_classifications_from_store recovers classifications written
    by the Gap Agent.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from efterlev.agents import (
    DocumentationAgent,
    DocumentationAgentInput,
    GapAgent,
    GapAgentInput,
    KsiClassification,
    reconstruct_classifications_from_store,
)
from efterlev.errors import AgentError
from efterlev.llm import StubLLMClient
from efterlev.models import Evidence, Indicator, SourceRef
from efterlev.provenance import ProvenanceStore, active_store


def _persist_evidence(store: ProvenanceStore, evidence: list[Evidence]) -> None:
    """Write each Evidence to the store so the 2026-04-23 store-level
    `validate_claim_provenance` check has records to resolve against."""
    for ev in evidence:
        store.write_record(
            payload=ev.model_dump(mode="json"),
            record_type="evidence",
            primitive=f"{ev.detector_id}@0.1.0",
        )


def _ev(ksi: str = "KSI-SVC-VRI", resource: str = "audit") -> Evidence:
    return Evidence.create(
        detector_id="aws.encryption_s3_at_rest",
        source_ref=SourceRef(file=Path("main.tf"), line_start=1, line_end=10),
        ksis_evidenced=[ksi],
        controls_evidenced=["SC-28"],
        content={"resource_name": resource, "encryption_state": "present"},
        timestamp=datetime(2026, 4, 21, tzinfo=UTC),
    )


def _ind(ksi_id: str = "KSI-SVC-VRI") -> Indicator:
    return Indicator(
        id=ksi_id,
        theme="SVC",
        name="Validating Resource Integrity",
        statement="Use cryptographic methods to validate resource integrity.",
        controls=["SC-13"],
    )


def _clf(
    ksi_id: str = "KSI-SVC-VRI",
    status: str = "partial",
    evidence_ids: list[str] | None = None,
) -> KsiClassification:
    # KsiClassification's positive-status-requires-evidence invariant
    # (gap.py 2026-04-25): implemented/partial must cite ≥1 evidence_id.
    # Default a placeholder when callers don't override and status is
    # positive — keeps fixture ergonomics while honoring the invariant.
    if evidence_ids is None and status in ("implemented", "partial"):
        evidence_ids = ["sha256:" + "0" * 64]
    return KsiClassification(
        ksi_id=ksi_id,
        status=status,  # type: ignore[arg-type]
        rationale="Encryption config present but procedural integrity unverified.",
        evidence_ids=evidence_ids or [],
    )


def _canned_narrative(evidence_id: str) -> str:
    # evidence_id is already "sha256:<hex>" (see compute_content_id).
    return json.dumps(
        {
            "narrative": (
                "The S3 audit bucket has server-side encryption configured with "
                "AES256 (evidence "
                + evidence_id
                + "). The scanner does not cover key-rotation procedures or "
                "KMS key-management practices, which remain unverified."
            ),
            "cited_evidence_ids": [evidence_id],
        }
    )


# -- happy path --------------------------------------------------------------


def test_documentation_agent_drafts_attestation_for_each_eligible_ksi(
    tmp_path: Path,
) -> None:
    ev = _ev()
    stub = StubLLMClient(response_text=_canned_narrative(ev.evidence_id), model="stub-opus")
    with ProvenanceStore(tmp_path) as store, active_store(store):
        _persist_evidence(store, [ev])
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[ev],
                classifications=[_clf(evidence_ids=[ev.evidence_id])],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )

    assert len(report.attestations) == 1
    att = report.attestations[0]
    assert att.draft.mode == "agent_drafted"
    assert att.draft.status == "partial"
    assert att.draft.narrative is not None
    assert ev.evidence_id in att.draft.narrative
    assert len(att.draft.citations) == 1
    assert att.draft.citations[0].evidence_id == ev.evidence_id
    assert att.claim_record_id is not None


def test_documentation_agent_prompt_carries_ksi_classification_and_fenced_evidence(
    tmp_path: Path,
) -> None:
    ev = _ev()
    stub = StubLLMClient(response_text=_canned_narrative(ev.evidence_id))
    with ProvenanceStore(tmp_path) as store, active_store(store):
        _persist_evidence(store, [ev])
        agent = DocumentationAgent(client=stub)
        agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[ev],
                classifications=[_clf(evidence_ids=[ev.evidence_id])],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )
    user = stub.last_messages[0].content
    assert "KSI-SVC-VRI" in user
    assert '"status": "partial"' in user
    # Nonce is random per run; match with a regex (Phase 2 post-review fixup F).
    import re

    assert re.search(rf'<evidence_[0-9a-f]+ id="{re.escape(ev.evidence_id)}">', user)
    # System prompt mentions the fence trust model.
    assert "untrusted data" in stub.last_system


# -- filtering / skipping ---------------------------------------------------


def test_documentation_agent_skips_not_applicable(tmp_path: Path) -> None:
    ev = _ev()
    stub = StubLLMClient(response_text=_canned_narrative(ev.evidence_id))
    with ProvenanceStore(tmp_path) as store, active_store(store):
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[ev],
                classifications=[_clf(status="not_applicable")],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )
    assert report.attestations == []
    assert report.skipped_ksi_ids == ["KSI-SVC-VRI"]
    # No LLM call made for the NA classification.
    assert stub.call_count == 0


def test_documentation_agent_only_ksi_filters_to_named(tmp_path: Path) -> None:
    ev_a = _ev(ksi="KSI-SVC-VRI", resource="a")
    ev_b = _ev(ksi="KSI-SVC-SNT", resource="b")
    # Respond with the A narrative unconditionally; only A should get drafted.
    stub = StubLLMClient(response_text=_canned_narrative(ev_a.evidence_id))
    with ProvenanceStore(tmp_path) as store, active_store(store):
        _persist_evidence(store, [ev_a, ev_b])
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={
                    "KSI-SVC-VRI": _ind("KSI-SVC-VRI"),
                    "KSI-SVC-SNT": _ind("KSI-SVC-SNT"),
                },
                evidence=[ev_a, ev_b],
                classifications=[
                    _clf("KSI-SVC-VRI", evidence_ids=[ev_a.evidence_id]),
                    _clf("KSI-SVC-SNT", evidence_ids=[ev_b.evidence_id]),
                ],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
                only_ksi="KSI-SVC-VRI",
            )
        )
    assert len(report.attestations) == 1
    assert report.attestations[0].draft.ksi_id == "KSI-SVC-VRI"
    assert "KSI-SVC-SNT" in report.skipped_ksi_ids


def test_documentation_agent_skips_classification_with_unknown_ksi(tmp_path: Path) -> None:
    # If a classification references a KSI the current baseline doesn't load
    # (e.g. FRMR was renamed), the agent skips it rather than crashing.
    ev = _ev()
    stub = StubLLMClient(response_text=_canned_narrative(ev.evidence_id))
    with ProvenanceStore(tmp_path) as store, active_store(store):
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={},  # empty baseline
                evidence=[ev],
                classifications=[_clf()],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )
    assert report.attestations == []
    assert report.skipped_ksi_ids == ["KSI-SVC-VRI"]


# -- defensive --------------------------------------------------------------


def test_documentation_agent_rejects_fabricated_evidence_citation(tmp_path: Path) -> None:
    ev = _ev()
    bogus = json.dumps(
        {
            "narrative": "Encryption is implemented perfectly.",
            "cited_evidence_ids": ["sha256:0000000000000000000000000000000000000000"],
        }
    )
    stub = StubLLMClient(response_text=bogus)
    with (
        ProvenanceStore(tmp_path) as store,
        active_store(store),
        pytest.raises(AgentError, match="cites evidence IDs not present"),
    ):
        agent = DocumentationAgent(client=stub)
        agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[ev],
                classifications=[_clf()],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )


def test_documentation_agent_rejects_empty_citations_when_gap_cited_evidence(
    tmp_path: Path,
) -> None:
    """A narrative grounded in Gap-cited evidence must cite at least one of those ids.

    Mirrors `KsiClassification._positive_status_requires_evidence` on the Gap
    side. Without this check, a confidently-worded narrative lands in the
    persisted Claim with empty `derived_from`, breaking the provenance graph
    and leaving the human reader no evidence to verify against.
    """
    ev = _ev()
    bogus = json.dumps(
        {
            "narrative": "Encryption is implemented; the scanner found nothing missing.",
            "cited_evidence_ids": [],
        }
    )
    stub = StubLLMClient(response_text=bogus)
    with (
        ProvenanceStore(tmp_path) as store,
        active_store(store),
        pytest.raises(AgentError, match="empty cited_evidence_ids"),
    ):
        agent = DocumentationAgent(client=stub)
        agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[ev],
                classifications=[_clf(evidence_ids=[ev.evidence_id])],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )


def test_documentation_agent_includes_scan_coverage_note_when_recommended(
    tmp_path: Path,
) -> None:
    """When the underlying scan was HCL-mode against a module-composed
    codebase, the per-KSI prompt includes a 'Scan coverage note' block
    instructing the model to acknowledge coverage limitations in narratives
    of `not_implemented` KSIs. Priority 0 (2026-04-27)."""
    from efterlev.models import ScanSummary

    ev = _ev()
    summary = ScanSummary(scan_mode="hcl", resources_parsed=9, module_calls=11, evidence_count=1)
    stub = StubLLMClient(response_text=_canned_narrative(ev.evidence_id))
    with ProvenanceStore(tmp_path) as store, active_store(store):
        _persist_evidence(store, [ev])
        agent = DocumentationAgent(client=stub)
        agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[ev],
                classifications=[_clf(evidence_ids=[ev.evidence_id])],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
                scan_summary=summary,
            )
        )

    user = stub.last_messages[0].content
    assert "Scan coverage note" in user
    assert "11 `module` calls" in user
    assert "may reflect scanner coverage limits" in user


def test_documentation_agent_omits_scan_coverage_note_when_unnecessary(
    tmp_path: Path,
) -> None:
    """Plan-mode scans and resource-only HCL scans should not get the
    coverage-note block — the prompt stays focused on per-KSI evidence."""
    from efterlev.models import ScanSummary

    ev = _ev()
    summary = ScanSummary(scan_mode="plan", resources_parsed=20, module_calls=0, evidence_count=8)
    stub = StubLLMClient(response_text=_canned_narrative(ev.evidence_id))
    with ProvenanceStore(tmp_path) as store, active_store(store):
        _persist_evidence(store, [ev])
        agent = DocumentationAgent(client=stub)
        agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[ev],
                classifications=[_clf(evidence_ids=[ev.evidence_id])],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
                scan_summary=summary,
            )
        )

    user = stub.last_messages[0].content
    assert "Scan coverage note" not in user


def test_documentation_agent_allows_empty_citations_when_no_evidence_in_classification(
    tmp_path: Path,
) -> None:
    """`not_implemented` with no Gap-cited evidence is the legitimate empty-cite path.

    The narrative explains the absence of evidence rather than grounding a
    positive claim, so cited_evidence_ids may be empty.
    """
    response = json.dumps(
        {
            "narrative": "No evidence of resource-integrity validation was produced; "
            "this KSI requires an Evidence Manifest attestation to establish posture.",
            "cited_evidence_ids": [],
        }
    )
    stub = StubLLMClient(response_text=response)
    with ProvenanceStore(tmp_path) as store, active_store(store):
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[],
                classifications=[_clf(status="not_implemented", evidence_ids=[])],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )
    assert len(report.attestations) == 1
    assert report.attestations[0].draft.status == "not_implemented"


# -- Gap→Doc evidence attribution flow -------------------------------------


def test_doc_agent_honors_cross_ksi_evidence_citations(tmp_path: Path) -> None:
    """The Gap Agent can cite evidence outside a KSI's detector-default attribution.

    Concrete case from the first real govnotes-demo run: a CloudTrail
    evidence record is attributed by the detector to KSI-MLA-LET and
    KSI-MLA-OSM (the detector's default), but the Gap Agent reasoned
    that "CloudTrail logs modifications" is also relevant to KSI-CMT-LMC
    (change monitoring) and cited that record when classifying CMT-LMC.

    Under the old filter (ksis_evidenced contains ksi_id), the Doc Agent
    received an empty evidence list for CMT-LMC and narrated "Gap cited
    evidence but I don't have it" — incoherent with the classification.

    Under the new filter (evidence_id in clf.evidence_ids), cross-KSI
    reasoning flows through cleanly. Whatever Gap cites, Doc shows.
    """
    # Evidence attributed ONLY to MLA-LET (detector-default) but cited
    # by the classification for a different KSI.
    cloudtrail_ev = Evidence.create(
        detector_id="aws.cloudtrail_audit_logging",
        source_ref=SourceRef(file=Path("logging.tf"), line_start=103, line_end=123),
        ksis_evidenced=["KSI-MLA-LET"],  # notably NOT KSI-CMT-LMC
        controls_evidenced=["AU-2", "AU-12"],
        content={"cloudtrail_state": "present", "is_multi_region": True},
        timestamp=datetime(2026, 4, 21, tzinfo=UTC),
    )
    cmt_lmc_indicator = Indicator(
        id="KSI-CMT-LMC",
        theme="CMT",
        name="Logging Modifications to Configuration",
        statement="Log all modifications to machine-based information resources.",
        controls=["CM-3", "CM-4"],
    )
    classification = _clf(
        ksi_id="KSI-CMT-LMC",
        evidence_ids=[cloudtrail_ev.evidence_id],  # Gap Agent's cross-KSI citation
    )

    stub = StubLLMClient(response_text=_canned_narrative(cloudtrail_ev.evidence_id))
    with ProvenanceStore(tmp_path) as store, active_store(store):
        _persist_evidence(store, [cloudtrail_ev])
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={"KSI-CMT-LMC": cmt_lmc_indicator},
                evidence=[cloudtrail_ev],
                classifications=[classification],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )

    # The attestation must be drafted and cite the evidence — even though
    # the evidence record's ksis_evidenced does NOT contain KSI-CMT-LMC.
    assert len(report.attestations) == 1
    att = report.attestations[0]
    assert att.draft.ksi_id == "KSI-CMT-LMC"
    assert len(att.draft.citations) == 1
    assert att.draft.citations[0].evidence_id == cloudtrail_ev.evidence_id

    # The fenced evidence MUST appear in the prompt the Doc Agent sent.
    user = stub.last_messages[0].content
    import re

    assert re.search(rf'<evidence_[0-9a-f]+ id="{re.escape(cloudtrail_ev.evidence_id)}">', user)


def test_doc_agent_empty_evidence_when_classification_cites_nothing(tmp_path: Path) -> None:
    """A `not_implemented` classification with evidence_ids=[] gets no evidence.

    Correct behavior: the LLM drafts a narrative explaining the absence,
    the skeleton has zero citations, and nothing is fabricated. Locks in
    that the new filter doesn't silently reach back for evidence the
    classification didn't cite.
    """
    unrelated_ev = _ev()  # attributed to KSI-SVC-VRI, NOT cited by the classification
    classification = _clf(ksi_id="KSI-SVC-VRI", status="not_implemented", evidence_ids=[])
    stub = StubLLMClient(
        response_text=json.dumps(
            {
                "narrative": "No scanner evidence was produced for this KSI.",
                "cited_evidence_ids": [],
            }
        )
    )
    with ProvenanceStore(tmp_path) as store, active_store(store):
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[unrelated_ev],  # present in input but not cited
                classifications=[classification],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )

    att = report.attestations[0]
    assert att.draft.citations == []
    # The uncited evidence MUST NOT appear in the prompt — otherwise
    # the model could be tempted to cite evidence the Gap Agent didn't.
    user = stub.last_messages[0].content
    assert unrelated_ev.evidence_id not in user


# -- reconstruction from store ----------------------------------------------


def test_reconstruct_classifications_from_store_roundtrips_gap_output(tmp_path: Path) -> None:
    """Gap Agent writes → `iter_claims_by_metadata_kind` reads → reconstruct yields it back."""
    ev = _ev()
    gap_response = json.dumps(
        {
            "ksi_classifications": [
                {
                    "ksi_id": "KSI-SVC-VRI",
                    "status": "partial",
                    "rationale": "Infra encryption present; procedural layer unproven.",
                    "evidence_ids": [ev.evidence_id],
                }
            ],
            "unmapped_findings": [],
        }
    )
    gap_stub = StubLLMClient(response_text=gap_response)
    with ProvenanceStore(tmp_path) as store, active_store(store):
        _persist_evidence(store, [ev])
        GapAgent(client=gap_stub).run(GapAgentInput(indicators=[_ind()], evidence=[ev]))
        rows = store.iter_claims_by_metadata_kind("ksi_classification")

    classifications = reconstruct_classifications_from_store(rows)
    assert len(classifications) == 1
    clf = classifications[0]
    assert clf.ksi_id == "KSI-SVC-VRI"
    assert clf.status == "partial"
    # evidence_ids round-trip as-is (fence id == evidence_id == record_id),
    # so the Documentation Agent's fence-citation validator works end-to-end.
    assert clf.evidence_ids == [ev.evidence_id]


# --- v0.1.4: deterministic narrative for evidence_layer_inapplicable ---


def test_documentation_agent_uses_deterministic_narrative_for_inapplicable(
    tmp_path: Path,
) -> None:
    """`evidence_layer_inapplicable` KSIs get a deterministic narrative by
    default — no LLM call. v0.1.4 default-skip pattern saves Sonnet token
    cost on the 25-45 procedural KSIs that fall into this status on a
    typical 60-KSI run.
    """
    stub = StubLLMClient(response_text='{"narrative":"never called","cited_evidence_ids":[]}')
    with ProvenanceStore(tmp_path) as store, active_store(store):
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[],
                classifications=[_clf(status="evidence_layer_inapplicable", evidence_ids=[])],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )
    # The KSI gets an attestation entry — FRMR completeness preserved —
    # but the narrative was generated deterministically, not by the LLM.
    assert len(report.attestations) == 1
    att = report.attestations[0]
    assert att.draft.ksi_id == "KSI-SVC-VRI"
    assert att.draft.status == "evidence_layer_inapplicable"
    assert "DRAFT — requires human review" in att.draft.narrative
    assert "evidence_layer_inapplicable" in att.draft.narrative
    # Crucially: zero LLM calls for this classification.
    assert stub.call_count == 0


def test_documentation_agent_calls_llm_for_inapplicable_when_opted_in(
    tmp_path: Path,
) -> None:
    """`include_inapplicable_narratives=True` opts back into LLM-drafted
    narratives for inapplicable KSIs. Verifies the override switch works."""
    stub = StubLLMClient(response_text='{"narrative":"LLM-drafted","cited_evidence_ids":[]}')
    with ProvenanceStore(tmp_path) as store, active_store(store):
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[],
                classifications=[_clf(status="evidence_layer_inapplicable", evidence_ids=[])],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
                include_inapplicable_narratives=True,
            )
        )
    assert len(report.attestations) == 1
    assert report.attestations[0].draft.narrative == "LLM-drafted"
    assert stub.call_count == 1
