"""`generate_frmr_skeleton` primitive tests.

Verifies the scanner-only path: evidence in, AttestationDraft with
`mode=scanner_only`, narrative=None, status=None out. Also checks the
line-range formatting edge cases (single line, range, absent) and that
the primitive emits the usual deterministic-primitive provenance record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from efterlev.errors import PrimitiveError
from efterlev.models import Evidence, SourceRef
from efterlev.primitives.generate import (
    GenerateFrmrSkeletonInput,
    generate_frmr_skeleton,
)
from efterlev.provenance import ProvenanceStore, active_store


def _ev(
    *,
    detector_id: str = "aws.encryption_s3_at_rest",
    file: str = "main.tf",
    line_start: int | None = 1,
    line_end: int | None = 10,
    resource: str = "audit",
) -> Evidence:
    return Evidence.create(
        detector_id=detector_id,
        source_ref=SourceRef(file=Path(file), line_start=line_start, line_end=line_end),
        ksis_evidenced=["KSI-SVC-VRI"],
        controls_evidenced=["SC-28"],
        content={"resource_name": resource, "encryption_state": "present"},
        timestamp=datetime(2026, 4, 21, tzinfo=UTC),
    )


def test_skeleton_emits_scanner_only_draft_with_citations(tmp_path: Path) -> None:
    ev = _ev()
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = generate_frmr_skeleton(
            GenerateFrmrSkeletonInput(
                ksi_id="KSI-SVC-VRI",
                evidence=[ev],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )

    draft = result.draft
    assert draft.mode == "scanner_only"
    assert draft.narrative is None
    assert draft.status is None
    assert draft.ksi_id == "KSI-SVC-VRI"
    assert draft.baseline_id == "fedramp-20x-moderate"
    assert draft.frmr_version == "0.9.43-beta"
    assert len(draft.citations) == 1
    cite = draft.citations[0]
    assert cite.evidence_id == ev.evidence_id
    assert cite.detector_id == "aws.encryption_s3_at_rest"
    assert cite.source_file == "main.tf"
    assert cite.source_lines == "1-10"


def test_skeleton_empty_evidence_produces_empty_citations_list(tmp_path: Path) -> None:
    # A KSI with no attributed evidence still yields a valid skeleton;
    # the Documentation Agent will later render this as "no evidence found."
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = generate_frmr_skeleton(
            GenerateFrmrSkeletonInput(
                ksi_id="KSI-SVC-SNT",
                evidence=[],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )
    assert result.draft.citations == []
    assert result.draft.mode == "scanner_only"


def test_skeleton_line_range_single_line(tmp_path: Path) -> None:
    ev = _ev(line_start=42, line_end=42)
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = generate_frmr_skeleton(
            GenerateFrmrSkeletonInput(
                ksi_id="KSI-SVC-VRI",
                evidence=[ev],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )
    assert result.draft.citations[0].source_lines == "42"


def test_skeleton_line_range_missing_is_none(tmp_path: Path) -> None:
    ev = _ev(line_start=None, line_end=None)
    with ProvenanceStore(tmp_path) as store, active_store(store):
        result = generate_frmr_skeleton(
            GenerateFrmrSkeletonInput(
                ksi_id="KSI-SVC-VRI",
                evidence=[ev],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )
    assert result.draft.citations[0].source_lines is None


def test_skeleton_persists_primitive_invocation_record(tmp_path: Path) -> None:
    ev = _ev()
    with ProvenanceStore(tmp_path) as store, active_store(store):
        generate_frmr_skeleton(
            GenerateFrmrSkeletonInput(
                ksi_id="KSI-SVC-VRI",
                evidence=[ev],
                baseline_id="fedramp-20x-moderate",
                frmr_version="0.9.43-beta",
            )
        )
        record_ids = store.iter_records()
    # Exactly one record: the primitive's own invocation. The skeleton
    # primitive itself doesn't write Evidence — that's the detector's job
    # and happens before this primitive runs.
    assert len(record_ids) == 1


def test_skeleton_rejects_non_input_model() -> None:
    with pytest.raises(PrimitiveError, match="expected input"):
        generate_frmr_skeleton({"ksi_id": "KSI-SVC-VRI"})  # type: ignore[arg-type]
