# `aws.centralized_log_aggregation`

Emits one workspace-scoped Evidence summarizing whether the codebase
declares centralized log aggregation: log-producing resources
(CloudWatch log groups, CloudTrails, flow logs) AND log-aggregating
resources (Security Hub, log destinations, subscription filters,
OpenSearch/Elasticsearch, Kinesis Firehose).

## Why this detector exists

KSI-MLA-OSM ("Operating SIEM Capability") asks: *"Operate a Security
Information and Event Management (SIEM) or similar system(s) for
centralized, tamper-resistant logging of events, activities, and
changes."* SIEM operation is fundamentally a runtime concern, but the
IaC layer can evidence the *commitment* — that log producers exist and
centralization primitives are declared to receive them.

Surfaced by the 2026-04-28 dogfood run against `/tmp/tf-vpc-test`. The
agent narrative for KSI-MLA-OSM read: *"Inventory shows
aws_cloudwatch_log_group resources but no SIEM aggregation primitives
... visible."* The existing detector library had nothing surfacing
aggregation primitives. This fills the gap.

## What this detector evidences

- **KSI-MLA-OSM** (Operating SIEM Capability) — partial cross-mapping.
- **800-53 controls (always):** AU-2 (Event Logging), AU-3 (Content of
  Audit Records), AU-4 (Audit Storage Capacity).
- **800-53 controls (conditional):** SI-4(2) (Automated Tools for
  Real-Time Analysis), SI-4(4) (Communications Traffic) — only when
  the workspace reaches the `aggregated` state (both producers and
  aggregators present).

## Resource categories

**Log producers:**
- `aws_cloudwatch_log_group` — application + service logs sink.
- `aws_cloudtrail` — control-plane audit trail.
- `aws_flow_log` — VPC network flow logs.

**Log aggregators:**
- `aws_securityhub_account` — multi-region findings aggregation.
- `aws_securityhub_finding_aggregator` — explicit cross-region setup.
- `aws_cloudwatch_log_destination` — cross-account log shipping.
- `aws_cloudwatch_log_subscription_filter` — real-time log streaming.
- `aws_kinesis_firehose_delivery_stream` — Firehose-based ingestion.
- `aws_opensearch_domain` / `aws_elasticsearch_domain` — search-backed
  SIEM backend.

## Aggregation states

| State | Meaning | Controls evidenced |
|---|---|---|
| `aggregated` | both log producers and aggregators present | AU-2, AU-3, AU-4, SI-4(2), SI-4(4) |
| `producers_only` | logs produced but no centralization primitive declared | AU-2, AU-3, AU-4 (gap on SI-4) |
| `aggregators_only` | aggregation declared but no producers in this workspace | AU-2, AU-3, AU-4 (gap on producer side) |

When neither category appears in the workspace, the detector emits
zero Evidence — the absence flows naturally to the Gap Agent, which
should classify KSI-MLA-OSM as `evidence_layer_inapplicable` for
workspaces that have no logging surface at all (rare for FedRAMP
ICP-A customers, but possible).

## What it does NOT prove

- **That the SIEM is actually operating.** Querying logs, firing
  alerts, retaining for the right period, surviving tampering attempts —
  all runtime concerns. Pair with procedural Evidence Manifests
  covering the SIEM runtime + on-call discipline.
- **Tamper-resistance.** The KSI statement explicitly mentions
  "tamper-resistant logging." This detector evidences the
  centralization side; pair with `aws.cloudtrail_log_file_validation`
  for the tamper-resistance slice.
- **Retention adequacy.** AU-11 (Audit Record Retention) is in the
  KSI's control list. Storage capacity declaration ≠ retention
  policy verification.
- **Log-flow correctness.** A subscription filter declared in
  Terraform doesn't itself prove logs are reaching the destination
  at runtime.
- **Coverage completeness.** The KSI's threat model asks for
  "events, activities, and changes" — application-layer events
  (auth failures, business-logic anomalies) typically come from
  application code, not from IaC primitives. Detector signals the
  CSP infrastructure layer only.

## Example

Input:

```hcl
resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/app/api"
  retention_in_days = 90
}

resource "aws_cloudtrail" "audit" {
  name           = "primary-audit"
  s3_bucket_name = "audit-trail-bucket"
}

resource "aws_securityhub_account" "main" {}

resource "aws_cloudwatch_log_subscription_filter" "to_siem" {
  name           = "ship-to-siem"
  log_group_name = aws_cloudwatch_log_group.app.name
  filter_pattern = ""
  destination_arn = aws_kinesis_firehose_delivery_stream.siem.arn
}

resource "aws_kinesis_firehose_delivery_stream" "siem" {
  name        = "siem-ingest"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn   = "arn:aws:iam::1:role/firehose"
    bucket_arn = "arn:aws:s3:::siem-archive"
  }
}
```

Output:

```json
{
  "detector_id": "aws.centralized_log_aggregation",
  "ksis_evidenced": ["KSI-MLA-OSM"],
  "controls_evidenced": ["AU-2", "AU-3", "AU-4", "SI-4(2)", "SI-4(4)"],
  "content": {
    "resource_type": "centralized_log_aggregation",
    "resource_name": "(workspace)",
    "aggregation_state": "aggregated",
    "log_producer_count": 2,
    "log_producers_by_type": {
      "aws_cloudwatch_log_group": 1,
      "aws_cloudtrail": 1
    },
    "aggregator_count": 3,
    "aggregators_by_type": {
      "aws_securityhub_account": 1,
      "aws_cloudwatch_log_subscription_filter": 1,
      "aws_kinesis_firehose_delivery_stream": 1
    }
  }
}
```

## Fixtures

- `fixtures/should_match/aggregated.tf` — both producers and
  aggregators → `aggregated`.
- `fixtures/should_match/producers_only.tf` — log groups and
  CloudTrail without aggregators → `producers_only` with gap.
- `fixtures/should_match/aggregators_only.tf` — Security Hub
  without producers → `aggregators_only` with gap.
- `fixtures/should_not_match/no_logging.tf` — neither category → 0
  Evidence emitted.
