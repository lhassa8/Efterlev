"""JSON sidecar tests for Gap Report output.

The JSON sidecar mirrors `render_gap_report_html`'s data view but emits
a schema-versioned, machine-readable structure suitable for tool
integration (3PAO ingest, custom dashboards). Tests verify that:

  - schema_version is set
  - all top-level fields are present with the expected types
  - boundary states resolve identically to the HTML renderer's view
  - the output is JSON-serializable (round-trip safe)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from efterlev.agents import GapReport
from efterlev.agents.gap import KsiClassification, UnmappedFinding
from efterlev.models import Evidence, SourceRef
from efterlev.reports import GAP_REPORT_JSON_SCHEMA_VERSION, render_gap_report_json


def _classification(**overrides: object) -> KsiClassification:
    base: dict[str, object] = {
        "ksi_id": "KSI-SVC-SNT",
        "status": "partial",
        "rationale": "TLS on HTTPS listener; HTTP listener exists without redirect.",
        "evidence_ids": ["sha256:" + "a" * 64],
    }
    base.update(overrides)
    return KsiClassification(**base)  # type: ignore[arg-type]


def _evidence(evidence_id: str, boundary_state: str = "boundary_undeclared") -> Evidence:
    """Build an Evidence with a specific boundary_state. Construct via __init__
    to set evidence_id directly (Evidence.create() recomputes the hash)."""
    return Evidence(
        evidence_id=evidence_id,
        detector_id="aws.tls_on_lb_listeners",
        ksis_evidenced=["KSI-SVC-SNT"],
        controls_evidenced=["SC-8"],
        source_ref=SourceRef(file=Path("main.tf"), line_start=1, line_end=10),
        content={"resource_type": "aws_lb_listener"},
        timestamp=datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC),
        boundary_state=boundary_state,  # type: ignore[arg-type]
    )


def _baseline_kwargs() -> dict:
    return {
        "baseline_id": "fedramp-20x-moderate",
        "frmr_version": "0.9.43-beta",
        "generated_at": datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC),
    }


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


# --- schema_version + top-level shape -------------------------------------


def test_schema_version_present_and_canonical() -> None:
    out = render_gap_report_json(_report(), **_baseline_kwargs())
    assert out["schema_version"] == GAP_REPORT_JSON_SCHEMA_VERSION
    assert out["schema_version"] == "1.0"
    assert out["report_type"] == "gap"


def test_top_level_keys_match_schema() -> None:
    out = render_gap_report_json(_report(), **_baseline_kwargs())
    expected = {
        "schema_version",
        "report_type",
        "generated_at",
        "baseline_id",
        "frmr_version",
        "workspace_boundary_state",
        "ksi_classifications",
        "unmapped_findings",
        "claim_record_ids",
    }
    assert set(out.keys()) == expected


def test_metadata_propagated() -> None:
    out = render_gap_report_json(_report(), **_baseline_kwargs())
    assert out["baseline_id"] == "fedramp-20x-moderate"
    assert out["frmr_version"] == "0.9.43-beta"
    assert out["generated_at"] == "2026-04-27T12:00:00+00:00"


# --- ksi_classifications --------------------------------------------------


def test_classification_serializes_all_fields() -> None:
    clf = _classification()
    out = render_gap_report_json(_report(classifications=[clf]), **_baseline_kwargs())
    assert len(out["ksi_classifications"]) == 1
    serialized = out["ksi_classifications"][0]
    assert serialized["ksi_id"] == "KSI-SVC-SNT"
    assert serialized["status"] == "partial"
    assert serialized["rationale"].startswith("TLS on HTTPS listener")
    assert serialized["evidence_ids"] == ["sha256:" + "a" * 64]
    assert serialized["boundary_state"] == "boundary_undeclared"


def test_classification_boundary_state_reflects_evidence_in_boundary() -> None:
    """When a cited evidence is in_boundary, the classification's
    boundary_state in the JSON sidecar is in_boundary."""
    eid = "sha256:" + "a" * 64
    clf = _classification(evidence_ids=[eid])
    ev = _evidence(eid, boundary_state="in_boundary")
    out = render_gap_report_json(
        _report(classifications=[clf]), evidence=[ev], **_baseline_kwargs()
    )
    assert out["ksi_classifications"][0]["boundary_state"] == "in_boundary"
    assert out["workspace_boundary_state"] == "in_boundary"


def test_classification_with_all_out_of_boundary_evidence_collapses_state() -> None:
    eid = "sha256:" + "b" * 64
    clf = _classification(evidence_ids=[eid])
    ev = _evidence(eid, boundary_state="out_of_boundary")
    out = render_gap_report_json(
        _report(classifications=[clf]), evidence=[ev], **_baseline_kwargs()
    )
    assert out["ksi_classifications"][0]["boundary_state"] == "out_of_boundary"


# --- unmapped_findings ----------------------------------------------------


def test_unmapped_findings_serialize() -> None:
    uf = UnmappedFinding(
        evidence_id="sha256:" + "c" * 64,
        controls=["SC-28", "SC-28(1)"],
        note="Encryption-at-rest finding without a KSI mapping in FRMR 0.9.43-beta.",
    )
    out = render_gap_report_json(_report(unmapped=[uf]), **_baseline_kwargs())
    assert len(out["unmapped_findings"]) == 1
    serialized = out["unmapped_findings"][0]
    assert serialized["evidence_id"] == "sha256:" + "c" * 64
    assert serialized["controls"] == ["SC-28", "SC-28(1)"]
    assert "Encryption-at-rest" in serialized["note"]


def test_claim_record_ids_serialize() -> None:
    out = render_gap_report_json(_report(claim_record_ids=["rec-1", "rec-2"]), **_baseline_kwargs())
    assert out["claim_record_ids"] == ["rec-1", "rec-2"]


# --- JSON-serializability -------------------------------------------------


def test_output_is_json_serializable() -> None:
    """The whole returned dict must round-trip through json.dumps without
    a TypeError. Pydantic enums (status) and Path objects (none here, but
    guarding) would break this if they leaked through."""
    clf = _classification()
    uf = UnmappedFinding(
        evidence_id="sha256:" + "d" * 64,
        controls=["SC-28"],
        note="x",
    )
    out = render_gap_report_json(
        _report(classifications=[clf], unmapped=[uf], claim_record_ids=["r1"]),
        **_baseline_kwargs(),
    )
    text = json.dumps(out, indent=2, sort_keys=True)
    # Round-trip preserves data.
    reparsed = json.loads(text)
    assert reparsed == out


def test_empty_report_serializes_cleanly() -> None:
    """An empty report (no classifications, no findings) still produces a
    valid JSON sidecar — useful for boundary-empty scans."""
    out = render_gap_report_json(_report(), **_baseline_kwargs())
    assert out["ksi_classifications"] == []
    assert out["unmapped_findings"] == []
    assert out["claim_record_ids"] == []
    # Round-trips.
    json.dumps(out)


# --- generated_at default -------------------------------------------------


def test_generated_at_defaults_to_now_when_absent() -> None:
    """When `generated_at` isn't passed, the renderer stamps now() — verify
    the output parses as a valid ISO timestamp."""
    kwargs = {k: v for k, v in _baseline_kwargs().items() if k != "generated_at"}
    out = render_gap_report_json(_report(), **kwargs)
    # Pydantic-shaped iso, e.g. "2026-04-27T19:30:00-04:00". Just verify
    # datetime.fromisoformat round-trips it.
    datetime.fromisoformat(out["generated_at"])
