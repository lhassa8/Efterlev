"""IAM-managed-via-Terraform detector.

Aggregates the customer's IAM resource declarations into a summary that
evidences "IAM under IaC management." KSI-IAM-AAM ("Automating Account
Management") asks the customer to manage account/role/group lifecycles
through automation rather than the AWS console; a Terraform codebase
declaring `aws_iam_*` resources IS that automation — every change goes
through `terraform plan` + `terraform apply`, the diff is reviewable,
and the state file is the authoritative record.

Sibling-pattern to `aws.terraform_inventory` (Priority 1.4) which
reports the workspace's overall inventory. This detector zooms into
IAM specifically because IAM-AAM is a distinct KSI with distinct
controls (AC-2 family) — surfacing IAM separately gives the Gap Agent
a focused signal rather than mixing into the broader inventory.

Empty IAM (no `aws_iam_*` declarations) emits no evidence — silence is
correct, the customer hasn't declared any IAM as code in this repo.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-IAM-AAM lists `ac-2.2`, `ac-2.3`, `ac-2.13`, `ac-6.7`, `ia-4.4`,
    `ia-12`, `ia-12.2`, `ia-12.3`, `ia-12.5` in its `controls` array.
    This detector evidences AC-2(2) (Automated System Account
    Management) directly. AC-2(3) (Disable Accounts) and beyond are
    runtime-state concerns; IA-12 (Identity Proofing) is procedural.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, SourceRef, TerraformResource

# IAM resource-type prefix — the broad family the detector inventories.
_IAM_PREFIX = "aws_iam_"


@detector(
    id="aws.iam_managed_via_terraform",
    ksis=["KSI-IAM-AAM"],
    controls=["AC-2(2)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one summary Evidence describing the workspace's IAM-via-Terraform posture.

    Evidences (800-53):  AC-2(2) (Automated System Account Management) —
                         the customer manages account/role/group/policy
                         lifecycles through declarative IaC rather than
                         manual console operations.
    Evidences (KSI):     KSI-IAM-AAM (Automating Account Management).
    Does NOT prove:      automated account-disable on suspicious activity
                         (that's KSI-IAM-SUS / AC-2(3)/AC-2(13)), identity
                         proofing rigor (IA-12 family — procedural), or
                         that IAM resources outside this codebase (other
                         repos, AWS Identity Center / SSO, manual console
                         users) are also managed via automation.
    """
    iam_resources = [r for r in resources if r.type.startswith(_IAM_PREFIX)]
    if not iam_resources:
        return []

    type_counts: Counter[str] = Counter(r.type for r in iam_resources)
    total = sum(type_counts.values())

    # Group counts into a `by_kind` summary keyed on canonical-shortform names
    # (users, roles, groups, policies, policy_attachments, ...). The shortform
    # makes the gap report's evidence card scannable; the full Counter is also
    # exposed for tooling consumers.
    by_kind: dict[str, int] = {}
    for tf_type, count in type_counts.items():
        # `aws_iam_role_policy_attachment` -> `role_policy_attachment`
        kind = tf_type[len(_IAM_PREFIX) :]
        by_kind[kind] = count

    # Source ref: anchor at the first IAM resource so the provenance walker
    # has a real on-disk file. The summary itself is workspace-scoped.
    first_ref = iam_resources[0].source_ref
    summary_ref = SourceRef(file=Path(first_ref.file))

    content: dict[str, Any] = {
        "resource_type": "iam_managed_via_terraform",
        "resource_name": "(workspace)",
        "automation_state": "tracked",
        "iam_resource_count": total,
        "distinct_iam_kinds": len(by_kind),
        "by_kind": by_kind,
    }

    return [
        Evidence.create(
            detector_id="aws.iam_managed_via_terraform",
            ksis_evidenced=["KSI-IAM-AAM"],
            controls_evidenced=["AC-2(2)"],
            source_ref=summary_ref,
            content=content,
            timestamp=datetime.now(UTC),
        )
    ]
