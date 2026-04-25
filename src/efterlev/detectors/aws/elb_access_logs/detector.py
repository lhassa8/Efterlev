"""ELB access-logs detector.

Inspects load-balancer resources (`aws_lb` / `aws_alb` for Application
and Network LBs; `aws_elb` for the legacy Classic LB) and surfaces
access-log configuration. Emits per-LB evidence distinguishing:

  - `enabled` — `access_logs.enabled = true` AND `access_logs.bucket`
    is configured.
  - `bucket_only` — bucket configured, enabled flag absent or false.
  - `absent` — no access-logs block at all (the AWS default for ALB/NLB).

KSI mapping per FRMR 0.9.43-beta:
  - KSI-MLA-LET (Logging Event Types) lists au-2 and au-12.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.elb_access_logs",
    ksis=["KSI-MLA-LET"],
    controls=["AU-2", "AU-12"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit per-LB Evidence for access-log configuration.

    Evidences (800-53):  AU-2 (Event Logging), AU-12 (Audit Record Generation).
    Evidences (KSI):     KSI-MLA-LET (Logging Event Types).
    Does NOT prove:      that the destination S3 bucket is itself
                         encrypted, retained appropriately, or has
                         lifecycle policies; that anyone reads the logs.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type in ("aws_lb", "aws_alb"):
            out.append(_classify_alb_nlb(r, now))
        elif r.type == "aws_elb":
            out.append(_classify_classic_elb(r, now))

    return out


def _classify_alb_nlb(r: TerraformResource, now: datetime) -> Evidence:
    """ALB/NLB: access logs configured via inline `access_logs` block."""
    block = r.get_nested("access_logs")
    enabled = None
    bucket = None
    if isinstance(block, dict):
        enabled = block.get("enabled")
        bucket = block.get("bucket")

    if enabled is True and bucket:
        log_state = "enabled"
    elif bucket and enabled is None:
        # AWS default: when `bucket` is set without `enabled`, AWS treats
        # `enabled = true`. Match that behavior.
        log_state = "enabled"
    elif bucket:
        log_state = "bucket_only"
    else:
        log_state = "absent"

    content: dict[str, Any] = {
        "resource_type": r.type,
        "resource_name": r.name,
        "lb_kind": "alb_or_nlb",
        "log_state": log_state,
        "bucket": _coerce_str(bucket),
    }
    if log_state == "absent":
        content["gap"] = "load balancer has no access_logs block; access logs are disabled"
    return Evidence.create(
        detector_id="aws.elb_access_logs",
        ksis_evidenced=["KSI-MLA-LET"],
        controls_evidenced=["AU-2", "AU-12"],
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )


def _classify_classic_elb(r: TerraformResource, now: datetime) -> Evidence:
    """Classic ELB: access logs configured via inline `access_logs` block."""
    block = r.get_nested("access_logs")
    enabled = None
    bucket = None
    interval = None
    if isinstance(block, dict):
        enabled = block.get("enabled")
        bucket = block.get("bucket")
        interval = block.get("interval")

    if (enabled is True and bucket) or (bucket and enabled is None):
        log_state = "enabled"
    elif bucket:
        log_state = "bucket_only"
    else:
        log_state = "absent"

    content: dict[str, Any] = {
        "resource_type": "aws_elb",
        "resource_name": r.name,
        "lb_kind": "classic",
        "log_state": log_state,
        "bucket": _coerce_str(bucket),
        "interval_minutes": interval if isinstance(interval, int) else None,
    }
    if log_state == "absent":
        content["gap"] = "classic ELB has no access_logs block; access logs are disabled"
    return Evidence.create(
        detector_id="aws.elb_access_logs",
        ksis_evidenced=["KSI-MLA-LET"],
        controls_evidenced=["AU-2", "AU-12"],
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
