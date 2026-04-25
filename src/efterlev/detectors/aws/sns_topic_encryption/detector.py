"""SNS topic encryption-at-rest detector.

Per `aws_sns_topic` resource, captures whether `kms_master_key_id` is
set and what kind of key reference it carries:

  - Customer-managed CMK reference (e.g., `aws_kms_key.app.arn`,
    or `alias/efterlev-app`) → strongest evidence.
  - AWS-managed default (`alias/aws/sns`) → partial — encryption is
    on, but the key is shared with other AWS services.
  - Attribute absent → AWS default encryption is applied automatically
    by AWS (no plaintext at rest), but the key is fully shared. We emit
    the absent-attr case as `aws_managed_default` evidence too.

KSI mapping per FRMR 0.9.43-beta:
  - SC-28 has no KSI mapping in 0.9.43-beta. Per the same precedent as
    `aws.encryption_s3_at_rest`, `ksis=[]` and we flag the FRMR mapping
    gap honestly in the README.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_AWS_MANAGED_ALIAS = "alias/aws/sns"


@detector(
    id="aws.sns_topic_encryption",
    ksis=[],
    controls=["SC-28"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence for each declared aws_sns_topic.

    Evidences (800-53):  SC-28 (Protection of Information at Rest).
    Evidences (KSI):     None — FRMR 0.9.43-beta has no KSI whose
                         `controls` array contains SC-28. Same precedent
                         as `aws.encryption_s3_at_rest`.
    Does NOT prove:      that subscribers' inboxes are also encrypted
                         (a separate concern); that messages are
                         encrypted in transit (SC-8 territory).
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_sns_topic":
            continue
        out.append(_classify(r, now))

    return out


def _classify(r: TerraformResource, now: datetime) -> Evidence:
    key_id = _coerce_str(r.body.get("kms_master_key_id"))

    if key_id is None or key_id == _AWS_MANAGED_ALIAS:
        encryption_state = "aws_managed_default"
    else:
        encryption_state = "customer_managed"

    return Evidence.create(
        detector_id="aws.sns_topic_encryption",
        ksis_evidenced=[],
        controls_evidenced=["SC-28"],
        source_ref=r.source_ref,
        content={
            "resource_type": "aws_sns_topic",
            "resource_name": r.name,
            "encryption_state": encryption_state,
            "kms_master_key_id": key_id,
        },
        timestamp=now,
    )


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
