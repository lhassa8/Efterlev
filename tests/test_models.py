"""Round-trip, ID-stability, and invariant tests for the internal data model.

Scope: every type in `efterlev.models` gets exercised on (a) construction via
`.create(...)` producing a valid id, (b) JSON round-trip preserving identity,
(c) content-sensitivity of the id, and (d) the small number of type-level
invariants the data model enforces (`Claim.requires_review` must stay True;
`Evidence.ksis_evidenced` may be empty for 800-53-only findings).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from efterlev.models import (
    Baseline,
    Claim,
    Control,
    ControlEnhancement,
    Evidence,
    Indicator,
    ProvenanceRecord,
    SourceRef,
    Theme,
)

# --- SourceRef -----------------------------------------------------------------


def test_source_ref_minimal_required_field() -> None:
    ref = SourceRef(file=Path("main.tf"))
    assert ref.file == Path("main.tf")
    assert ref.line_start is None
    assert ref.line_end is None
    assert ref.commit is None


def test_source_ref_round_trip() -> None:
    ref = SourceRef(file=Path("infra/s3.tf"), line_start=42, line_end=58, commit="abc123")
    restored = SourceRef.model_validate_json(ref.model_dump_json())
    assert restored == ref


# --- Evidence ------------------------------------------------------------------


def _fixed_ts() -> datetime:
    return datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)


def test_evidence_create_computes_id_with_sha256_prefix() -> None:
    ev = Evidence.create(
        detector_id="aws.encryption_s3_at_rest",
        source_ref=SourceRef(file=Path("main.tf"), line_start=1),
        controls_evidenced=["sc-28"],
        content={"resource": "prod_bucket", "encrypted": True},
        timestamp=_fixed_ts(),
    )
    assert ev.evidence_id.startswith("sha256:")
    assert len(ev.evidence_id) == len("sha256:") + 64


def test_evidence_id_is_deterministic_for_same_content() -> None:
    ts = _fixed_ts()
    ref = SourceRef(file=Path("main.tf"))

    def make() -> Evidence:
        return Evidence.create(
            detector_id="aws.encryption_s3_at_rest",
            source_ref=ref,
            controls_evidenced=["sc-28"],
            timestamp=ts,
        )

    assert make().evidence_id == make().evidence_id


def test_evidence_id_changes_with_any_content_change() -> None:
    ref = SourceRef(file=Path("main.tf"))
    ts = _fixed_ts()
    a = Evidence.create(detector_id="aws.a", source_ref=ref, timestamp=ts)
    b = Evidence.create(detector_id="aws.b", source_ref=ref, timestamp=ts)
    assert a.evidence_id != b.evidence_id


def test_evidence_ksis_evidenced_may_be_empty() -> None:
    # Supports the design-call-1 "800-53 only, no KSI maps here" case per
    # DECISIONS 2026-04-20. Pending Phase 2 decision, this must remain valid.
    ev = Evidence.create(
        detector_id="aws.encryption_s3_at_rest",
        source_ref=SourceRef(file=Path("main.tf")),
        controls_evidenced=["sc-28"],
        timestamp=_fixed_ts(),
    )
    assert ev.ksis_evidenced == []


def test_evidence_round_trip_preserves_id() -> None:
    ev = Evidence.create(
        detector_id="aws.encryption_s3_at_rest",
        source_ref=SourceRef(file=Path("main.tf"), line_start=10),
        ksis_evidenced=["KSI-SVC-VRI"],
        controls_evidenced=["sc-28", "sc-28.1"],
        content={"ok": True},
        timestamp=_fixed_ts(),
    )
    restored = Evidence.model_validate_json(ev.model_dump_json())
    assert restored.evidence_id == ev.evidence_id
    assert restored == ev


# --- Claim ---------------------------------------------------------------------


def _make_claim(**overrides: object) -> Claim:
    defaults: dict[str, object] = dict(
        claim_type="classification",
        content={"ksi": "KSI-SVC-SNT", "status": "implemented"},
        confidence="high",
        derived_from=["sha256:" + "a" * 64],
        model="claude-opus-4-7",
        prompt_hash="sha256:" + "b" * 64,
        timestamp=_fixed_ts(),
    )
    defaults.update(overrides)
    return Claim.create(**defaults)  # type: ignore[arg-type]


def test_claim_create_computes_id() -> None:
    claim = _make_claim()
    assert claim.claim_id.startswith("sha256:")
    assert claim.requires_review is True


def test_claim_requires_review_cannot_be_false() -> None:
    # Type-level enforcement: Literal[True] rejects any other value at validation.
    with pytest.raises(ValidationError):
        Claim(
            claim_id="",
            claim_type="classification",
            content={"x": 1},
            confidence="high",
            requires_review=False,  # type: ignore[arg-type]
            derived_from=[],
            model="claude-opus-4-7",
            prompt_hash="sha256:" + "0" * 64,
            timestamp=_fixed_ts(),
        )


def test_claim_round_trip_preserves_id() -> None:
    claim = _make_claim()
    restored = Claim.model_validate_json(claim.model_dump_json())
    assert restored == claim
    assert restored.claim_id == claim.claim_id


# --- ProvenanceRecord ----------------------------------------------------------


def test_provenance_record_create_computes_id() -> None:
    rec = ProvenanceRecord.create(
        record_type="evidence",
        content_ref=".efterlev/store/sha256/ab/cd/deadbeef",
        primitive="scan_terraform@0.1.0",
    )
    assert rec.record_id.startswith("sha256:")


def test_provenance_record_distinguishes_primitive_vs_agent_origin() -> None:
    rec_from_primitive = ProvenanceRecord.create(
        record_type="evidence",
        content_ref="cr1",
        primitive="scan_terraform@0.1.0",
        timestamp=_fixed_ts(),
    )
    rec_from_agent = ProvenanceRecord.create(
        record_type="claim",
        content_ref="cr2",
        agent="gap_agent",
        model="claude-opus-4-7",
        prompt_hash="sha256:" + "c" * 64,
        timestamp=_fixed_ts(),
    )
    assert rec_from_primitive.agent is None
    assert rec_from_agent.primitive is None
    assert rec_from_primitive.record_id != rec_from_agent.record_id


# --- Indicator / Theme / Baseline ---------------------------------------------


def test_indicator_round_trip() -> None:
    ind = Indicator(
        id="KSI-SVC-SNT",
        theme="SVC",
        name="Securing Network Traffic",
        statement="Encrypt or otherwise secure network traffic.",
        controls=["ac-1", "sc-8", "sc-8.1", "sc-13"],
        fka="KSI-SVC-02",
    )
    restored = Indicator.model_validate_json(ind.model_dump_json())
    assert restored == ind


def test_theme_minimal() -> None:
    theme = Theme(id="SVC", name="Service Configuration")
    assert theme.short_name is None
    assert theme.description is None


def test_baseline_holds_indicator_ids() -> None:
    baseline = Baseline(
        id="fedramp-20x-moderate",
        name="FedRAMP 20x Moderate",
        indicator_ids=["KSI-SVC-SNT", "KSI-SVC-VRI", "KSI-IAM-MFA"],
    )
    assert len(baseline.indicator_ids) == 3


# --- Control / ControlEnhancement ----------------------------------------------


def test_control_with_enhancements() -> None:
    ctrl = Control(
        id="sc-28",
        family="sc",
        title="Protection of Information at Rest",
        enhancements=[
            ControlEnhancement(id="sc-28.1", parent_id="sc-28", title="Cryptographic Protection"),
        ],
    )
    restored = Control.model_validate_json(ctrl.model_dump_json())
    assert restored == ctrl
    assert restored.enhancements[0].parent_id == "sc-28"


# --- Frozen / immutability ----------------------------------------------------


def test_evidence_is_frozen() -> None:
    ev = Evidence.create(
        detector_id="x",
        source_ref=SourceRef(file=Path("f")),
        timestamp=_fixed_ts(),
    )
    with pytest.raises(ValidationError):
        ev.detector_id = "y"  # type: ignore[misc]


def test_claim_is_frozen() -> None:
    claim = _make_claim()
    with pytest.raises(ValidationError):
        claim.confidence = "low"  # type: ignore[misc]


# --- ScanSummary (Priority 0, 2026-04-27) ---------------------------------


def test_scan_summary_recommend_plan_json_when_modules_outnumber_resources() -> None:
    """The dogfood-2026-04-27 worked example: 11 modules, 9 resources, HCL mode.
    Trigger condition fires; agents see the coverage note."""
    from efterlev.models import ScanSummary

    s = ScanSummary(scan_mode="hcl", resources_parsed=9, module_calls=11, evidence_count=1)
    assert s.recommend_plan_json is True


def test_scan_summary_recommend_plan_json_at_three_modules_threshold() -> None:
    """Even when resources outnumber modules, 3+ modules fire the warning —
    any non-trivial use of upstream modules already risks invisible workload."""
    from efterlev.models import ScanSummary

    s = ScanSummary(scan_mode="hcl", resources_parsed=10, module_calls=3, evidence_count=2)
    assert s.recommend_plan_json is True


def test_scan_summary_no_recommend_plan_json_when_resource_only() -> None:
    """A clean resource-only HCL scan should not surface the coverage note —
    nothing useful to suggest."""
    from efterlev.models import ScanSummary

    s = ScanSummary(scan_mode="hcl", resources_parsed=10, module_calls=0, evidence_count=4)
    assert s.recommend_plan_json is False


def test_scan_summary_no_recommend_plan_json_in_plan_mode() -> None:
    """Plan-mode scans never trigger the coverage note — modules are already
    expanded by `terraform show -json` so the threshold is meaningless there."""
    from efterlev.models import ScanSummary

    s = ScanSummary(scan_mode="plan", resources_parsed=20, module_calls=0, evidence_count=8)
    assert s.recommend_plan_json is False


def test_scan_summary_is_frozen() -> None:
    from efterlev.models import ScanSummary

    s = ScanSummary(scan_mode="hcl", resources_parsed=1, module_calls=0, evidence_count=0)
    with pytest.raises(ValidationError):
        s.module_calls = 99  # type: ignore[misc]
