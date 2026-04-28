"""JSON sidecar tests for Remediation Report output.

Mirrors test_gap_report_json.py and test_documentation_report_json.py.
The JSON sidecar gives downstream tooling (e.g., automation that
applies the proposed diff) the same data the HTML report renders.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from efterlev.agents import RemediationProposal
from efterlev.reports import (
    REMEDIATION_REPORT_JSON_SCHEMA_VERSION,
    render_remediation_proposal_json,
)

_DIFF = """\
--- a/main.tf
+++ b/main.tf
@@ -1,3 +1,4 @@
 resource "aws_s3_bucket" "data" {
   bucket = "example"
+  # remediation: explicit owner block
 }
"""


def _proposal(
    *,
    ksi_id: str = "KSI-SVC-SNT",
    status: str = "proposed",
    diff: str = _DIFF,
    explanation: str = "Adds an explicit owner block to the S3 bucket.",
    cited_evidence_ids: list[str] | None = None,
    cited_source_files: list[str] | None = None,
    claim_record_id: str | None = "rec-1",
) -> RemediationProposal:
    return RemediationProposal(
        ksi_id=ksi_id,
        status=status,  # type: ignore[arg-type]
        diff=diff,
        explanation=explanation,
        cited_evidence_ids=cited_evidence_ids or ["sha256:" + "a" * 64],
        cited_source_files=cited_source_files or ["main.tf"],
        claim_record_id=claim_record_id,
    )


def _kwargs() -> dict:
    return {
        "generated_at": datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC),
    }


# --- schema_version + top-level shape -------------------------------------


def test_schema_version_present_and_canonical() -> None:
    out = render_remediation_proposal_json(_proposal(), **_kwargs())
    assert out["schema_version"] == REMEDIATION_REPORT_JSON_SCHEMA_VERSION
    assert out["schema_version"] == "1.0"
    assert out["report_type"] == "remediation"


def test_top_level_keys_match_schema() -> None:
    out = render_remediation_proposal_json(_proposal(), **_kwargs())
    expected = {
        "schema_version",
        "report_type",
        "generated_at",
        "ksi_id",
        "status",
        "diff",
        "explanation",
        "cited_evidence_ids",
        "cited_source_files",
        "claim_record_id",
    }
    assert set(out.keys()) == expected


def test_metadata_propagated() -> None:
    out = render_remediation_proposal_json(_proposal(), **_kwargs())
    assert out["generated_at"] == "2026-04-27T12:00:00+00:00"
    assert out["ksi_id"] == "KSI-SVC-SNT"
    assert out["status"] == "proposed"


# --- proposal serialization -----------------------------------------------


def test_proposal_serializes_all_fields() -> None:
    out = render_remediation_proposal_json(
        _proposal(
            cited_evidence_ids=["sha256:" + "a" * 64, "sha256:" + "b" * 64],
            cited_source_files=["main.tf", "modules/network/vpc.tf"],
        ),
        **_kwargs(),
    )
    assert out["explanation"] == "Adds an explicit owner block to the S3 bucket."
    assert out["cited_evidence_ids"] == ["sha256:" + "a" * 64, "sha256:" + "b" * 64]
    assert out["cited_source_files"] == ["main.tf", "modules/network/vpc.tf"]
    assert out["claim_record_id"] == "rec-1"


def test_diff_preserved_verbatim() -> None:
    """The diff string must round-trip byte-for-byte through JSON so a
    consumer can write it to disk and `git apply` it directly."""
    out = render_remediation_proposal_json(_proposal(), **_kwargs())
    assert out["diff"] == _DIFF
    text = json.dumps(out)
    reparsed = json.loads(text)
    assert reparsed["diff"] == _DIFF


def test_no_terraform_fix_proposal_serializes() -> None:
    """A `no_terraform_fix` proposal still serializes — empty diff,
    explanation only."""
    out = render_remediation_proposal_json(
        _proposal(status="no_terraform_fix", diff="", explanation="Procedural gap."),
        **_kwargs(),
    )
    assert out["status"] == "no_terraform_fix"
    assert out["diff"] == ""
    assert out["explanation"] == "Procedural gap."


def test_proposal_without_claim_record_id_serializes_null() -> None:
    out = render_remediation_proposal_json(_proposal(claim_record_id=None), **_kwargs())
    assert out["claim_record_id"] is None


# --- JSON-serializability -------------------------------------------------


def test_output_is_json_serializable() -> None:
    out = render_remediation_proposal_json(_proposal(), **_kwargs())
    text = json.dumps(out, indent=2, sort_keys=True)
    reparsed = json.loads(text)
    assert reparsed == out


def test_generated_at_defaults_to_now_when_absent() -> None:
    out = render_remediation_proposal_json(_proposal())
    datetime.fromisoformat(out["generated_at"])
