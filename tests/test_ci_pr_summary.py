"""Tests for `scripts/ci_pr_summary.py` — the GitHub Action's PR-comment
formatter.

The script loads evidence directly from the on-disk store (SQLite DB +
content-addressed blob files) rather than via the Efterlev Python API,
so it runs from a CI shell even when the package install is in a
different virtualenv. These tests construct a real store, populate it
with evidence + optional classifications, and verify the rendered
markdown.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from efterlev.models import Evidence, SourceRef
from efterlev.provenance import ProvenanceStore

# The script isn't installed as a package; add scripts/ to sys.path so
# we can import its functions for white-box testing.
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ci_pr_summary import (  # noqa: E402  — sys.path manipulated above
    _is_finding,
    _short_detector,
    build_summary_markdown,
)


def _seed_store(tmp_path: Path) -> Path:
    """Create a `.efterlev/` dir with a ProvenanceStore; return the dir path."""
    efterlev_dir = tmp_path / ".efterlev"
    efterlev_dir.parent.mkdir(parents=True, exist_ok=True)
    # ProvenanceStore expects a parent that it creates `.efterlev/` under.
    return efterlev_dir


def _write_evidence(
    store: ProvenanceStore,
    detector_id: str,
    content: dict,
    *,
    source_file: str = "main.tf",
    line_start: int | None = 10,
    line_end: int | None = 14,
) -> None:
    """Shortcut: build + persist one Evidence record."""
    ev = Evidence.create(
        detector_id=detector_id,
        source_ref=SourceRef(file=source_file, line_start=line_start, line_end=line_end),
        ksis_evidenced=[],
        controls_evidenced=["SC-28"],
        content=content,
        timestamp=datetime.now(UTC),
    )
    store.write_record(
        payload=ev.model_dump(mode="json"),
        record_type="evidence",
        primitive=f"{detector_id}@0.1.0",
    )


# --- _is_finding classifier ------------------------------------------------


def test_explicit_gap_field_is_finding() -> None:
    assert _is_finding({"content": {"gap": "something wrong"}}) is True


def test_encryption_absent_is_finding() -> None:
    assert _is_finding({"content": {"encryption_state": "absent"}}) is True


def test_encryption_present_is_not_finding() -> None:
    assert _is_finding({"content": {"encryption_state": "present"}}) is False


def test_rotation_disabled_is_finding() -> None:
    assert _is_finding({"content": {"rotation_status": "disabled"}}) is True


def test_rotation_enabled_is_not_finding() -> None:
    assert _is_finding({"content": {"rotation_status": "enabled"}}) is False


def test_mfa_absent_is_finding() -> None:
    assert _is_finding({"content": {"mfa_required": "absent"}}) is True


def test_posture_partial_is_finding() -> None:
    assert _is_finding({"content": {"posture": "partial"}}) is True


def test_posture_fully_blocked_is_not_finding() -> None:
    assert _is_finding({"content": {"posture": "fully_blocked"}}) is False


def test_fips_absent_is_finding() -> None:
    assert _is_finding({"content": {"fips_state": "absent"}}) is True


def test_tls_absent_is_finding() -> None:
    assert _is_finding({"content": {"tls_state": "absent"}}) is True


def test_empty_content_is_not_finding() -> None:
    assert _is_finding({"content": {}}) is False


# --- _short_detector -------------------------------------------------------


def test_short_detector_strips_namespace() -> None:
    assert _short_detector("aws.encryption_s3_at_rest") == "encryption_s3_at_rest"


def test_short_detector_handles_bare_id() -> None:
    assert _short_detector("custom_check") == "custom_check"


# --- build_summary_markdown: end-to-end -----------------------------------


def test_markdown_renders_findings_table(tmp_path: Path) -> None:
    efterlev_dir = _seed_store(tmp_path)
    with ProvenanceStore(tmp_path) as store:
        # Finding: absent encryption.
        _write_evidence(
            store,
            "aws.encryption_s3_at_rest",
            {
                "resource_name": "user_uploads",
                "encryption_state": "absent",
                "gap": "bucket declared without inline server_side_encryption_configuration",
            },
            source_file="infra/main.tf",
            line_start=42,
            line_end=55,
        )
        # Non-finding: present.
        _write_evidence(
            store,
            "aws.encryption_s3_at_rest",
            {"resource_name": "audit_logs", "encryption_state": "present"},
        )

    markdown, stats = build_summary_markdown(efterlev_dir)

    assert "## 🧪 Efterlev compliance scan" in markdown
    assert "### Findings (1)" in markdown
    assert "encryption_s3_at_rest" in markdown
    assert "user_uploads" in markdown
    # Source location is surfaced in the findings row.
    assert "infra/main.tf:42-55" in markdown
    assert stats["findings"] == 1
    assert stats["detectors"] == 1


def test_markdown_groups_by_detector_in_coverage_table(tmp_path: Path) -> None:
    efterlev_dir = _seed_store(tmp_path)
    with ProvenanceStore(tmp_path) as store:
        _write_evidence(store, "aws.encryption_s3_at_rest", {"encryption_state": "present"})
        _write_evidence(store, "aws.encryption_s3_at_rest", {"encryption_state": "present"})
        _write_evidence(store, "aws.tls_on_lb_listeners", {"tls_state": "present"})

    markdown, stats = build_summary_markdown(efterlev_dir)

    # Coverage table shows one row per detector with the right count.
    assert "| `encryption_s3_at_rest` | 2 |" in markdown
    assert "| `tls_on_lb_listeners` | 1 |" in markdown
    assert stats["detectors"] == 2


def test_markdown_no_findings_produces_clean_marker(tmp_path: Path) -> None:
    efterlev_dir = _seed_store(tmp_path)
    with ProvenanceStore(tmp_path) as store:
        _write_evidence(store, "aws.encryption_s3_at_rest", {"encryption_state": "present"})

    markdown, stats = build_summary_markdown(efterlev_dir)

    assert "Detectors ran clean" in markdown
    assert stats["findings"] == 0


def test_markdown_includes_ksi_classifications_section(tmp_path: Path) -> None:
    efterlev_dir = _seed_store(tmp_path)
    with ProvenanceStore(tmp_path) as store:
        _write_evidence(
            store,
            "aws.encryption_s3_at_rest",
            {"encryption_state": "absent", "gap": "missing sse"},
        )
        # Gap Agent classifications — shape that the CLI writes.
        store.write_record(
            payload={
                "claim_id": "sha256:aaaa",
                "claim_type": "classification",
                "content": {
                    "ksi_id": "KSI-SVC-VRI",
                    "status": "partial",
                    "rationale": "mixed evidence",
                },
                "confidence": "medium",
                "derived_from": [],
                "model": "claude-opus-4-7",
                "prompt_hash": "dummy",
                "requires_review": True,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            record_type="claim",
            agent="gap_agent@0.1.0",
            metadata={"kind": "ksi_classification", "ksi_id": "KSI-SVC-VRI"},
        )
        store.write_record(
            payload={
                "claim_id": "sha256:bbbb",
                "claim_type": "classification",
                "content": {
                    "ksi_id": "KSI-SVC-SNT",
                    "status": "not_implemented",
                    "rationale": "no evidence",
                },
                "confidence": "medium",
                "derived_from": [],
                "model": "claude-opus-4-7",
                "prompt_hash": "dummy",
                "requires_review": True,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            record_type="claim",
            agent="gap_agent@0.1.0",
            metadata={"kind": "ksi_classification", "ksi_id": "KSI-SVC-SNT"},
        )

    markdown, stats = build_summary_markdown(efterlev_dir)

    assert "### KSI classifications (Gap Agent)" in markdown
    assert "| `partial` | 1 |" in markdown
    assert "| `not_implemented` | 1 |" in markdown
    assert stats["classifications"] == 2


def test_markdown_skips_ksi_section_when_no_classifications(tmp_path: Path) -> None:
    # Scanner-only run: no Gap Agent claims. The KSI section must not
    # appear (don't render an empty table).
    efterlev_dir = _seed_store(tmp_path)
    with ProvenanceStore(tmp_path) as store:
        _write_evidence(store, "aws.encryption_s3_at_rest", {"encryption_state": "present"})

    markdown, stats = build_summary_markdown(efterlev_dir)

    assert "KSI classifications" not in markdown
    assert stats["classifications"] == 0


def test_markdown_excludes_manifest_evidence_from_findings(tmp_path: Path) -> None:
    # Manifest attestations (detector_id="manifest") are not detector
    # findings and should not appear in the findings table.
    efterlev_dir = _seed_store(tmp_path)
    with ProvenanceStore(tmp_path) as store:
        # Direct write of manifest-shaped evidence — the real loader uses
        # detector_id="manifest".
        ev = Evidence.create(
            detector_id="manifest",
            source_ref=SourceRef(
                file=".efterlev/manifests/security-inbox.yml", line_start=1, line_end=20
            ),
            ksis_evidenced=["KSI-AFR-FSI"],
            controls_evidenced=[],
            content={"statement": "SOC monitors inbox", "attested_by": "vp-security"},
            timestamp=datetime.now(UTC),
        )
        store.write_record(
            payload=ev.model_dump(mode="json"),
            record_type="evidence",
            primitive="load_evidence_manifests@0.1.0",
        )
        _write_evidence(
            store,
            "aws.encryption_s3_at_rest",
            {"encryption_state": "absent", "gap": "missing sse"},
        )

    markdown, stats = build_summary_markdown(efterlev_dir)

    # Only the detector finding counts; manifest evidence is excluded
    # from both detectors count and findings count.
    assert stats["findings"] == 1
    assert stats["detectors"] == 1
    assert "manifest" not in markdown


def test_missing_store_raises_file_not_found_error(tmp_path: Path) -> None:
    # No `.efterlev/store.db` → explicit FileNotFoundError with a
    # helpful message.
    import pytest

    with pytest.raises(FileNotFoundError, match="did `efterlev scan` run"):
        build_summary_markdown(tmp_path / "nonexistent")


def test_markdown_contains_draft_disclaimer(tmp_path: Path) -> None:
    efterlev_dir = _seed_store(tmp_path)
    with ProvenanceStore(tmp_path) as store:
        _write_evidence(store, "aws.encryption_s3_at_rest", {"encryption_state": "present"})

    markdown, _ = build_summary_markdown(efterlev_dir)

    # Every output must carry the "draft findings; reviewer must confirm"
    # marker — applies the drafts-not-authorizations discipline to the
    # PR-comment surface.
    assert "draft findings" in markdown
    assert "qualified reviewer" in markdown
