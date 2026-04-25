"""IAM Access Analyzer detector.

Emits Evidence for each `aws_accessanalyzer_analyzer` resource. Captures
whether the analyzer is ACCOUNT-scoped (default) or ORGANIZATION-scoped
(broader coverage, stronger evidence).

KSI mapping per FRMR 0.9.43-beta:
  - KSI-CNA-EIS (Enforcing Intended State) — ca-7 is listed. Access
    Analyzer is a continuous-monitoring service for IAM policies; clean
    fit for CA-7.
"""

from __future__ import annotations

from datetime import UTC, datetime

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.access_analyzer_enabled",
    ksis=["KSI-CNA-EIS"],
    controls=["CA-7", "AC-6"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence for each declared aws_accessanalyzer_analyzer.

    Evidences (800-53):  CA-7 (Continuous Monitoring), AC-6 (Least Privilege).
    Evidences (KSI):     KSI-CNA-EIS (Enforcing Intended State).
    Does NOT prove:      that findings are reviewed; that the analyzer's
                         scope (account vs organization) matches the
                         compliance-boundary's expectations; that
                         findings surface through a response workflow.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_accessanalyzer_analyzer":
            continue
        out.append(_emit_analyzer_evidence(r, now))

    return out


def _emit_analyzer_evidence(r: TerraformResource, now: datetime) -> Evidence:
    scope = r.body.get("type", "ACCOUNT")
    if not isinstance(scope, str):
        scope = "ACCOUNT"

    return Evidence.create(
        detector_id="aws.access_analyzer_enabled",
        ksis_evidenced=["KSI-CNA-EIS"],
        controls_evidenced=["CA-7", "AC-6"],
        source_ref=r.source_ref,
        content={
            "resource_type": "aws_accessanalyzer_analyzer",
            "resource_name": r.name,
            "analyzer_state": "declared",
            "scope": scope,
            "stronger_org_scope": scope == "ORGANIZATION",
        },
        timestamp=now,
    )
