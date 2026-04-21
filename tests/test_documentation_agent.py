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


def _clf(ksi_id: str = "KSI-SVC-VRI", status: str = "partial") -> KsiClassification:
    return KsiClassification(
        ksi_id=ksi_id,
        status=status,  # type: ignore[arg-type]
        rationale="Encryption config present but procedural integrity unverified.",
        evidence_ids=[],
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
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={"KSI-SVC-VRI": _ind()},
                evidence=[ev],
                classifications=[_clf()],
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
    user = stub.last_messages[0].content
    assert "KSI-SVC-VRI" in user
    assert '"status": "partial"' in user
    assert f'<evidence id="{ev.evidence_id}">' in user
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
        agent = DocumentationAgent(client=stub)
        report = agent.run(
            DocumentationAgentInput(
                indicators={
                    "KSI-SVC-VRI": _ind("KSI-SVC-VRI"),
                    "KSI-SVC-SNT": _ind("KSI-SVC-SNT"),
                },
                evidence=[ev_a, ev_b],
                classifications=[_clf("KSI-SVC-VRI"), _clf("KSI-SVC-SNT")],
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
