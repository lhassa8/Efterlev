# `aws.cloudwatch_alarms_critical`

Inventories `aws_cloudwatch_metric_alarm` resources.

## What this detector evidences

- **KSI-MLA-OSM** (Operating SIEM Capability) and **KSI-MLA-LET** (Logging Event Types).
- **800-53 controls:** SI-4, SI-4(2), SI-4(4), AU-6(1).

## What it proves

Every `aws_cloudwatch_metric_alarm` resource declared in the Terraform is emitted as one Evidence record, capturing its metric name, namespace, comparison operator, threshold, and whether at least one `alarm_actions` entry is configured.

## What it does NOT prove

- That the alarm's metric-filter pattern actually matches what it intends to.
- That the SNS topic referenced by `alarm_actions` is monitored by a human (or anything at all).
- That the FedRAMP-recommended alarm set (Root account usage, IAM policy changes, unauthorized API calls, console logins without MFA) is fully covered. Inventory-plus-Gap-Agent-reasoning handles that question.
- Alarms that cross-reference CloudTrail metric filters (common pattern) have their pattern-matching logic in a separate `aws_cloudwatch_log_metric_filter` resource which this detector does not (yet) ingest.

## Detection signal

Every resource of type `aws_cloudwatch_metric_alarm` produces one Evidence record with `alarm_state="declared"`. There is no negative signal — absence of any alarm produces zero Evidence, and the Gap Agent handles "no alarms declared" as its own judgment call.

## Known limitations

- Coverage reasoning is deliberately punted to the Gap Agent. A scanner-only view of alarm-set completeness would require encoding the full FedRAMP-recommended alarm taxonomy in the detector, which couples the detector to a specific control framework's evolving guidance. Inventory emission keeps the detector aligned with the "deterministic, narrow" principle.
- `aws_cloudwatch_log_metric_filter` resources are not inventoried here — they're a separate surface. A follow-up detector can be added if demand surfaces.
