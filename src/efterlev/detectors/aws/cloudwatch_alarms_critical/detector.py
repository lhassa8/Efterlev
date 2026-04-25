"""CloudWatch alarms detector.

Inventories `aws_cloudwatch_metric_alarm` resources. Each alarm becomes
one Evidence record with its metric name, namespace, threshold, and
whether it has at least one alarm action configured. The Gap Agent
reasons about coverage (e.g., "do you have alarms for the
FedRAMP-recommended event set?"); the detector just inventories.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-MLA-OSM (Operating SIEM Capability) — SI-4 is listed.
  - KSI-MLA-LET (Logging Event Types) — AU-2 / AU-12 are listed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.cloudwatch_alarms_critical",
    ksis=["KSI-MLA-OSM", "KSI-MLA-LET"],
    controls=["SI-4", "SI-4(2)", "SI-4(4)", "AU-6(1)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one Evidence per aws_cloudwatch_metric_alarm found.

    Evidences (800-53):  SI-4 (Information System Monitoring),
                         SI-4(2) (Automated Tools and Mechanisms),
                         SI-4(4) (Inbound/Outbound Communications),
                         AU-6(1) (Automated Process Integration).
    Evidences (KSI):     KSI-MLA-OSM, KSI-MLA-LET.
    Does NOT prove:      that the alarms have valid SNS subscriptions;
                         that anyone reads the alerts; that the metric
                         filter pattern matches what it's intended to;
                         that the FedRAMP-recommended alarm set is
                         fully covered — that's the Gap Agent's job.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_cloudwatch_metric_alarm":
            continue
        out.append(_inventory_alarm(r, now))

    return out


def _inventory_alarm(r: TerraformResource, now: datetime) -> Evidence:
    body = r.body

    alarm_actions = body.get("alarm_actions")
    has_alarm_action = bool(alarm_actions) and alarm_actions not in ([], [[]])

    return Evidence.create(
        detector_id="aws.cloudwatch_alarms_critical",
        ksis_evidenced=["KSI-MLA-OSM", "KSI-MLA-LET"],
        controls_evidenced=["SI-4", "SI-4(2)", "SI-4(4)", "AU-6(1)"],
        source_ref=r.source_ref,
        content={
            "resource_type": "aws_cloudwatch_metric_alarm",
            "resource_name": r.name,
            "alarm_state": "declared",
            "metric_name": _coerce_str(body.get("metric_name")),
            "namespace": _coerce_str(body.get("namespace")),
            "comparison_operator": _coerce_str(body.get("comparison_operator")),
            "threshold": body.get("threshold"),
            "has_alarm_action": has_alarm_action,
        },
        timestamp=now,
    )


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
