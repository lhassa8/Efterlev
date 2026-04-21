"""Tests for the @detector decorator and its registry.

Detectors produce `list[Evidence]`; the decorator enforces that shape and
persists every Evidence into the active provenance store when one is bound.
Tests clear the detector registry between runs to prevent cross-test leakage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from efterlev.detectors.base import (
    DetectorSpec,
    clear_registry,
    detector,
    get_registry,
)
from efterlev.errors import DetectorError
from efterlev.models import Evidence, SourceRef
from efterlev.provenance import ProvenanceStore, active_store


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    clear_registry()


def _fake_evidence(detector_id: str = "aws.fake", controls: list[str] | None = None) -> Evidence:
    return Evidence.create(
        detector_id=detector_id,
        source_ref=SourceRef(file=Path("main.tf"), line_start=1),
        controls_evidenced=controls or ["sc-28"],
        content={"ok": True},
        timestamp=datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC),
    )


# --- registration contract ----------------------------------------------------


def test_decorator_registers_detector_metadata() -> None:
    @detector(
        id="aws.fake_detector",
        ksis=["KSI-SVC-VRI"],
        controls=["SC-28", "SC-28(1)"],
        source="terraform",
        version="0.1.0",
    )
    def detect(resources: list[object]) -> list[Evidence]:
        return []

    reg = get_registry()
    assert "aws.fake_detector" in reg
    spec = reg["aws.fake_detector"]
    assert isinstance(spec, DetectorSpec)
    assert spec.ksis == ("KSI-SVC-VRI",)
    assert spec.controls == ("SC-28", "SC-28(1)")
    assert spec.source == "terraform"
    assert spec.spec_name == "aws.fake_detector@0.1.0"


def test_decorator_allows_empty_ksis_for_unmapped_control() -> None:
    # Per DECISIONS 2026-04-20 design call #1 — SC-28 has no KSI in FRMR 0.9.43-beta.
    # A detector must be declarable with ksis=[] rather than by inventing a KSI.
    @detector(
        id="aws.unmapped_detector",
        ksis=[],
        controls=["SC-28"],
        source="terraform",
        version="0.1.0",
    )
    def detect(resources: list[object]) -> list[Evidence]:
        return []

    assert get_registry()["aws.unmapped_detector"].ksis == ()


def test_decorator_rejects_empty_controls() -> None:
    with pytest.raises(DetectorError, match="must declare at least one 800-53 control"):

        @detector(
            id="aws.no_controls",
            ksis=["KSI-SVC-VRI"],
            controls=[],
            source="terraform",
            version="0.1.0",
        )
        def detect(resources: list[object]) -> list[Evidence]:
            return []


def test_decorator_rejects_non_dotted_id() -> None:
    with pytest.raises(DetectorError, match="must be dotted"):

        @detector(
            id="not_dotted",
            ksis=["KSI-SVC-VRI"],
            controls=["SC-28"],
            source="terraform",
            version="0.1.0",
        )
        def detect(resources: list[object]) -> list[Evidence]:
            return []


def test_decorator_rejects_duplicate_ids() -> None:
    @detector(
        id="aws.dup",
        ksis=[],
        controls=["SC-28"],
        source="terraform",
        version="0.1.0",
    )
    def detect_a(resources: list[object]) -> list[Evidence]:
        return []

    with pytest.raises(DetectorError, match="already registered"):

        @detector(
            id="aws.dup",
            ksis=[],
            controls=["SC-28"],
            source="terraform",
            version="0.1.0",
        )
        def detect_b(resources: list[object]) -> list[Evidence]:
            return []


# --- call-time type enforcement -----------------------------------------------


def test_wrapper_raises_when_detector_returns_non_list() -> None:
    @detector(
        id="aws.lies",
        ksis=[],
        controls=["SC-28"],
        source="terraform",
        version="0.1.0",
    )
    def detect(resources: list[object]) -> list[Evidence]:
        return "not a list"  # type: ignore[return-value]

    with pytest.raises(DetectorError, match="must return list\\[Evidence\\]"):
        detect([])


def test_wrapper_raises_when_detector_returns_list_of_non_evidence() -> None:
    @detector(
        id="aws.lies_harder",
        ksis=[],
        controls=["SC-28"],
        source="terraform",
        version="0.1.0",
    )
    def detect(resources: list[object]) -> list[Evidence]:
        return [{"not": "evidence"}]  # type: ignore[list-item]

    with pytest.raises(DetectorError, match="must return list\\[Evidence\\]"):
        detect([])


# --- provenance emission ------------------------------------------------------


def test_active_store_persists_every_evidence_returned(tmp_path: Path) -> None:
    @detector(
        id="aws.emit_two",
        ksis=["KSI-SVC-VRI"],
        controls=["SC-28"],
        source="terraform",
        version="0.1.0",
    )
    def detect(resources: list[object]) -> list[Evidence]:
        return [_fake_evidence(), _fake_evidence()]

    with ProvenanceStore(tmp_path) as store, active_store(store):
        out = detect([])
        assert len(out) == 2
        ids = store.iter_records()
        assert len(ids) == 2
        rec = store.get_record(ids[0])
        assert rec is not None
        assert rec.record_type == "evidence"
        assert rec.primitive == "aws.emit_two@0.1.0"


def test_no_active_store_warns_but_still_returns_evidence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @detector(
        id="aws.standalone",
        ksis=[],
        controls=["SC-28"],
        source="terraform",
        version="0.1.0",
    )
    def detect(resources: list[object]) -> list[Evidence]:
        return [_fake_evidence()]

    with caplog.at_level("WARNING", logger="efterlev.detectors.base"):
        out = detect([])
    assert len(out) == 1
    assert "no active provenance store" in caplog.text
