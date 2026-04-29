"""Centralized log-aggregation posture detector.

KSI-MLA-OSM ("Operating SIEM Capability") asks providers to operate a
SIEM (or similar system) for centralized, tamper-resistant logging of
events, activities, and changes. SIEM operation is fundamentally a
runtime concern; what IaC can evidence is the *commitment* — that
log-producing resources exist AND that centralization primitives
(Security Hub, log destinations, log-streaming, OpenSearch domains)
are declared to receive them.

The detector emits one workspace-scoped Evidence summarizing:

  - Log-producing resource counts (CloudWatch log groups, CloudTrails,
    flow logs, ELB access-log buckets).
  - Aggregation-primitive counts (Security Hub, log destinations,
    subscription filters, Kinesis Firehose, OpenSearch/Elasticsearch).
  - A coarse `aggregation_state` enum:
      `aggregated`       — both producers and aggregators present.
      `producers_only`   — logs produced but no centralization in IaC.
      `aggregators_only` — aggregation declared but no producers in
                           this workspace (logs may flow in from
                           another workspace / account).
      `none_declared`    — neither — detector emits no evidence (KSI
                           probably evidence_layer_inapplicable for
                           workspaces with no logging surface at all).

Honest scope: surfacing IaC-layer aggregation primitives is positive
evidence of *intent*, not of *operation*. A 3PAO consuming this
Evidence still needs procedural Evidence Manifests covering: the SIEM
runtime (queries, alerts, on-call), retention enforcement,
tamper-resistance attestation (or pair with
`aws.cloudtrail_log_file_validation` for that slice), and the actual
event-flow coverage.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-MLA-OSM (Operating SIEM Capability) — partial cross-mapping
    via AU-2 (Event Logging), AU-3 (Content of Audit Records), AU-4
    (Audit Storage Capacity), and SI-4 (System Monitoring) at the
    declaration layer. The KSI's full control list is 18 entries; this
    detector evidences the centralization slice (AU-2, AU-3, AU-4,
    SI-4(2), SI-4(4)).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, SourceRef, TerraformResource

# Resource types that produce logs Efterlev recognizes.
_LOG_PRODUCER_TYPES = frozenset(
    {
        "aws_cloudwatch_log_group",
        "aws_cloudtrail",
        "aws_flow_log",
    }
)

# Resource types that participate in log centralization / aggregation.
# Each carries different evidence weight; the detector reports counts
# rather than collapsing to a single boolean so a 3PAO can read the
# specific primitive shapes.
_AGGREGATOR_TYPES = frozenset(
    {
        "aws_securityhub_account",
        "aws_securityhub_finding_aggregator",
        "aws_cloudwatch_log_destination",
        "aws_cloudwatch_log_subscription_filter",
        "aws_kinesis_firehose_delivery_stream",
        "aws_opensearch_domain",
        "aws_elasticsearch_domain",
    }
)


@detector(
    id="aws.centralized_log_aggregation",
    ksis=["KSI-MLA-OSM"],
    controls=["AU-2", "AU-3", "AU-4", "SI-4(2)", "SI-4(4)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one workspace-scoped Evidence describing log-aggregation posture.

    Evidences (800-53):  AU-2 (Event Logging), AU-3 (Content of Audit
                         Records), AU-4 (Audit Storage Capacity),
                         SI-4(2) (Automated Tools and Mechanisms for
                         Real-Time Analysis), SI-4(4) (Inbound and
                         Outbound Communications Traffic) at the IaC
                         declaration layer.
    Evidences (KSI):     KSI-MLA-OSM (Operating SIEM Capability),
                         partial cross-mapping.
    Does NOT prove:      that the SIEM is actually operating — querying
                         logs, firing alerts, retaining for the right
                         period, surviving tampering attempts. Those
                         are runtime concerns. Pair with procedural
                         Evidence Manifests + `aws.cloudtrail_log_file_validation`
                         (tamper-resistance) for full KSI evidence.
                         Does not include ELB access-log destinations
                         in the producer count — that's covered by
                         `aws.elb_access_logs`.
    """
    producers = _count_by_type(resources, _LOG_PRODUCER_TYPES)
    aggregators = _count_by_type(resources, _AGGREGATOR_TYPES)

    producer_total = sum(producers.values())
    aggregator_total = sum(aggregators.values())

    if producer_total == 0 and aggregator_total == 0:
        return []

    state = _classify_state(producer_total, aggregator_total)

    # Anchor source_ref at the first matching resource so the provenance
    # walker has something concrete to resolve. If only one side has
    # resources, anchor there.
    anchor = _first_anchor(resources, _LOG_PRODUCER_TYPES | _AGGREGATOR_TYPES)
    summary_ref = SourceRef(file=Path(anchor.file) if anchor else Path("(workspace)"))

    controls = ["AU-2", "AU-3", "AU-4"]
    if state == "aggregated":
        controls.extend(["SI-4(2)", "SI-4(4)"])

    content: dict[str, Any] = {
        "resource_type": "centralized_log_aggregation",
        "resource_name": "(workspace)",
        "aggregation_state": state,
        "log_producer_count": producer_total,
        "log_producers_by_type": producers,
        "aggregator_count": aggregator_total,
        "aggregators_by_type": aggregators,
    }
    gap = _gap_text_for(state, producer_total, aggregator_total)
    if gap is not None:
        content["gap"] = gap

    return [
        Evidence.create(
            detector_id="aws.centralized_log_aggregation",
            ksis_evidenced=["KSI-MLA-OSM"],
            controls_evidenced=controls,
            source_ref=summary_ref,
            content=content,
            timestamp=datetime.now(UTC),
        )
    ]


def _count_by_type(resources: list[TerraformResource], wanted: frozenset[str]) -> dict[str, int]:
    """Return `{resource_type: count}` for resources whose type is in `wanted`.

    Special case: `aws_kinesis_firehose_delivery_stream` is treated as an
    aggregator only when its source includes CloudWatch logs OR S3 logs.
    A Firehose with a Kinesis-stream-only source is application telemetry,
    not log centralization, and shouldn't count for this KSI. We can't
    fully resolve the Firehose source statically (it's a separate field),
    so we count all Firehose declarations and let the agent / reviewer
    interpret in context.
    """
    counts: dict[str, int] = {}
    for r in resources:
        if r.type in wanted:
            counts[r.type] = counts.get(r.type, 0) + 1
    return counts


def _classify_state(producer_total: int, aggregator_total: int) -> str:
    if producer_total > 0 and aggregator_total > 0:
        return "aggregated"
    if producer_total > 0 and aggregator_total == 0:
        return "producers_only"
    return "aggregators_only"


def _gap_text_for(state: str, producer_total: int, aggregator_total: int) -> str | None:
    if state == "aggregated":
        return None
    if state == "producers_only":
        return (
            f"{producer_total} log-producing resource(s) declared but no "
            "centralization primitive (Security Hub / log destination / "
            "subscription filter / OpenSearch / Firehose) found in this "
            "workspace. Logs reach a SIEM only if forwarded by infrastructure "
            "declared elsewhere."
        )
    # aggregators_only
    return (
        f"{aggregator_total} aggregation primitive(s) declared but no "
        "log-producing resources (CloudWatch log groups, CloudTrail, "
        "flow logs) found in this workspace. The aggregation may be "
        "operating on logs from another account or workspace."
    )


def _first_anchor(resources: list[TerraformResource], types: frozenset[str]) -> SourceRef | None:
    for r in resources:
        if r.type in types:
            return r.source_ref
    return None
