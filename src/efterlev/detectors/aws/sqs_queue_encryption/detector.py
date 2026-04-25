"""SQS queue encryption-at-rest detector.

Mirror of `aws.sns_topic_encryption` for `aws_sqs_queue`. SQS supports
two encryption modes:

  - SSE-KMS via `kms_master_key_id`: AWS-managed default
    (`alias/aws/sqs`) or customer-managed CMK.
  - SSE-SQS (managed by SQS itself): set via `sqs_managed_sse_enabled =
    true`. AWS introduced this as a simpler alternative to SSE-KMS;
    treated as `sqs_managed_sse` evidence-state — equivalent to
    AWS-managed-default for SC-28 purposes.

KSI mapping per FRMR 0.9.43-beta:
  - SC-28 has no KSI mapping. `ksis=[]` per the SC-28 precedent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_AWS_MANAGED_ALIAS = "alias/aws/sqs"


@detector(
    id="aws.sqs_queue_encryption",
    ksis=[],
    controls=["SC-28"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence for each declared aws_sqs_queue.

    Evidences (800-53):  SC-28 (Protection of Information at Rest).
    Evidences (KSI):     None — SC-28 unmapped in FRMR 0.9.43-beta.
    Does NOT prove:      that producers/consumers handle messages
                         securely after dequeue; that messages are
                         encrypted in transit (SC-8 territory); the
                         appropriateness of the queue-policy.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_sqs_queue":
            continue
        out.append(_classify(r, now))

    return out


def _classify(r: TerraformResource, now: datetime) -> Evidence:
    body = r.body
    key_id = _coerce_str(body.get("kms_master_key_id"))
    sqs_managed_sse = body.get("sqs_managed_sse_enabled")

    encryption_state: str
    if key_id and key_id != _AWS_MANAGED_ALIAS:
        encryption_state = "customer_managed"
    elif key_id == _AWS_MANAGED_ALIAS:
        encryption_state = "aws_managed_default"
    elif sqs_managed_sse is True:
        encryption_state = "sqs_managed_sse"
    elif key_id is None and sqs_managed_sse is None:
        # Neither SSE-KMS nor SSE-SQS configured — no encryption at rest.
        encryption_state = "absent"
    else:
        encryption_state = "absent"

    content: dict[str, Any] = {
        "resource_type": "aws_sqs_queue",
        "resource_name": r.name,
        "encryption_state": encryption_state,
        "kms_master_key_id": key_id,
        "sqs_managed_sse_enabled": bool(sqs_managed_sse) if sqs_managed_sse is not None else None,
    }
    if encryption_state == "absent":
        content["gap"] = (
            "queue has no kms_master_key_id and no sqs_managed_sse_enabled — "
            "messages are not encrypted at rest"
        )

    return Evidence.create(
        detector_id="aws.sqs_queue_encryption",
        ksis_evidenced=[],
        controls_evidenced=["SC-28"],
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
