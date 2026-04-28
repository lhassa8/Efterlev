"""JSON sidecar tests for Documentation Report output.

Mirrors the gap-report JSON sidecar tests at test_gap_report_json.py.
The JSON sidecar gives downstream tooling the same data the HTML
report renders, in a schema-versioned, machine-readable shape.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from efterlev.agents import DocumentationReport, KsiAttestation
from efterlev.models import AttestationCitation, AttestationDraft
from efterlev.reports import (
    DOCUMENTATION_REPORT_JSON_SCHEMA_VERSION,
    render_documentation_report_json,
)


def _citation(
    evidence_id: str = "sha256:" + "a" * 64,
    detector_id: str = "aws.tls_on_lb_listeners",
    source_file: str = "main.tf",
    source_lines: str | None = "12-24",
) -> AttestationCitation:
    return AttestationCitation(
        evidence_id=evidence_id,
        detector_id=detector_id,
        source_file=source_file,
        source_lines=source_lines,
    )


def _draft(
    *,
    ksi_id: str = "KSI-SVC-SNT",
    status: str | None = "partial",
    narrative: str | None = "TLS is configured on the main listener.",
    citations: list[AttestationCitation] | None = None,
    controls_evidenced: list[str] | None = None,
) -> AttestationDraft:
    return AttestationDraft(
        ksi_id=ksi_id,
        baseline_id="fedramp-20x-moderate",
        frmr_version="0.9.43-beta",
        mode="agent_drafted",
        citations=citations or [],
        controls_evidenced=controls_evidenced or [],
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
        "generated_at": datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC),
    }


# --- schema_version + top-level shape -------------------------------------


def test_schema_version_present_and_canonical() -> None:
    out = render_documentation_report_json(_report(), **_kwargs())
    assert out["schema_version"] == DOCUMENTATION_REPORT_JSON_SCHEMA_VERSION
    assert out["schema_version"] == "1.0"
    assert out["report_type"] == "documentation"


def test_top_level_keys_match_schema() -> None:
    out = render_documentation_report_json(_report(), **_kwargs())
    expected = {
        "schema_version",
        "report_type",
        "generated_at",
        "baseline_id",
        "frmr_version",
        "attestations",
        "skipped_ksi_ids",
    }
    assert set(out.keys()) == expected


def test_metadata_propagated() -> None:
    out = render_documentation_report_json(_report(), **_kwargs())
    assert out["baseline_id"] == "fedramp-20x-moderate"
    assert out["frmr_version"] == "0.9.43-beta"
    assert out["generated_at"] == "2026-04-27T12:00:00+00:00"


# --- attestation serialization --------------------------------------------


def test_attestation_serializes_all_fields() -> None:
    att = KsiAttestation(
        draft=_draft(
            citations=[_citation()],
            controls_evidenced=["SC-8"],
        ),
        claim_record_id="rec-1",
    )
    out = render_documentation_report_json(_report(attestations=[att]), **_kwargs())
    assert len(out["attestations"]) == 1
    serialized = out["attestations"][0]
    assert serialized["ksi_id"] == "KSI-SVC-SNT"
    assert serialized["status"] == "partial"
    assert serialized["mode"] == "agent_drafted"
    assert serialized["narrative"].startswith("TLS is configured")
    assert serialized["controls_evidenced"] == ["SC-8"]
    assert serialized["claim_record_id"] == "rec-1"
    assert len(serialized["citations"]) == 1
    cite = serialized["citations"][0]
    assert cite["evidence_id"] == "sha256:" + "a" * 64
    assert cite["detector_id"] == "aws.tls_on_lb_listeners"
    assert cite["source_file"] == "main.tf"
    assert cite["source_lines"] == "12-24"


def test_attestation_with_no_claim_record_id_serializes_null() -> None:
    """A drafted attestation without a persisted claim record id (e.g.,
    rendered before persistence) shows null in JSON."""
    att = KsiAttestation(draft=_draft(), claim_record_id=None)
    out = render_documentation_report_json(_report(attestations=[att]), **_kwargs())
    assert out["attestations"][0]["claim_record_id"] is None


def test_attestation_with_no_citations_emits_empty_list() -> None:
    att = KsiAttestation(draft=_draft(citations=[]), claim_record_id="rec-2")
    out = render_documentation_report_json(_report(attestations=[att]), **_kwargs())
    assert out["attestations"][0]["citations"] == []


def test_scanner_only_attestation_with_null_status_and_narrative() -> None:
    """The scanner_only mode keeps status and narrative as None — propagate."""
    att = KsiAttestation(
        draft=AttestationDraft(
            ksi_id="KSI-MLA-LET",
            baseline_id="fedramp-20x-moderate",
            frmr_version="0.9.43-beta",
            mode="scanner_only",
            citations=[],
            controls_evidenced=[],
            status=None,
            narrative=None,
        ),
        claim_record_id=None,
    )
    out = render_documentation_report_json(_report(attestations=[att]), **_kwargs())
    serialized = out["attestations"][0]
    assert serialized["status"] is None
    assert serialized["narrative"] is None
    assert serialized["mode"] == "scanner_only"


# --- skipped + empty cases ------------------------------------------------


def test_skipped_ksi_ids_serialize() -> None:
    out = render_documentation_report_json(
        _report(skipped=["KSI-AFR-FSI", "KSI-CED-CAS"]), **_kwargs()
    )
    assert out["skipped_ksi_ids"] == ["KSI-AFR-FSI", "KSI-CED-CAS"]


def test_empty_report_serializes_cleanly() -> None:
    out = render_documentation_report_json(_report(), **_kwargs())
    assert out["attestations"] == []
    assert out["skipped_ksi_ids"] == []
    json.dumps(out)


# --- JSON-serializability -------------------------------------------------


def test_output_is_json_serializable() -> None:
    """Round-trip through json.dumps preserves data."""
    att = KsiAttestation(
        draft=_draft(
            citations=[_citation(), _citation(evidence_id="sha256:" + "b" * 64)],
            controls_evidenced=["SC-8", "SC-13"],
        ),
        claim_record_id="rec-3",
    )
    out = render_documentation_report_json(
        _report(attestations=[att], skipped=["KSI-AFR-FSI"]),
        **_kwargs(),
    )
    text = json.dumps(out, indent=2, sort_keys=True)
    reparsed = json.loads(text)
    assert reparsed == out


def test_generated_at_defaults_to_now_when_absent() -> None:
    kwargs = {k: v for k, v in _kwargs().items() if k != "generated_at"}
    out = render_documentation_report_json(_report(), **kwargs)
    datetime.fromisoformat(out["generated_at"])
