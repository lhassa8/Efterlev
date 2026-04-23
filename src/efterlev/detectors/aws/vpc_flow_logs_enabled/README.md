# aws.vpc_flow_logs_enabled

Scans `aws_flow_log` resources and records network-layer logging
configuration: which target (VPC / subnet / ENI), what traffic is
captured, and where the logs are sent.

## What it proves

- **AU-2 (Event Logging)** at the network layer — the VPC/subnet/ENI
  traffic is being captured to a logging destination.
- **AU-12 (Audit Record Generation)** at the network layer — flow log
  records are generated for the declared target.

## What it does NOT prove

- **Coverage.** The detector does not check whether every VPC in the
  repo has a flow log — only that declared flow logs exist. The Gap
  Agent cross-references `aws_vpc` resources to flow logs at reasoning
  time (mirroring the bucket↔public-access-block pattern).
- **Log retention policy** on the destination bucket / log group.
  That's the `backup_retention_configured` detector's adjacency for S3,
  and a separate concern for CloudWatch Logs retention.
- **Destination security.** If flow logs go to an S3 bucket with no
  object-lock and public-read, the logs are worth little. The
  `s3_public_access_block` detector covers that adjacent concern.
- **Runtime state.** Only the declaration is examined.

## KSI mapping

**KSI-MLA-LET (Logging Event Types).** FRMR 0.9.43-beta lists au-2 and
au-12 in its `controls` array, and the KSI's statement is "Maintain a
list of information resources and event types that will be logged,
monitored, and audited, then do so." Clean mapping.

## Traffic type nuance

`traffic_type = "REJECT"` captures only denied packets — valuable for
security signal but NOT sufficient on its own for full event logging,
which typically requires `ALL`. The detector records the traffic type
verbatim so the Gap Agent can weight the evidence appropriately.

## Example

Input:

```hcl
resource "aws_flow_log" "main" {
  vpc_id               = aws_vpc.main.id
  traffic_type         = "ALL"
  log_destination_type = "s3"
  log_destination      = "arn:aws:s3:::flow-logs-bucket"
}
```

Output:

```json
{
  "detector_id": "aws.vpc_flow_logs_enabled",
  "ksis_evidenced": ["KSI-MLA-LET"],
  "controls_evidenced": ["AU-2", "AU-12"],
  "content": {
    "resource_type": "aws_flow_log",
    "resource_name": "main",
    "target_kind": "vpc",
    "target_ref": "${aws_vpc.main.id}",
    "traffic_type": "ALL",
    "destination_type": "s3"
  }
}
```

## Fixtures

- `fixtures/should_match/` — flow logs with ALL traffic to a
  destination.
- `fixtures/should_not_match/` — .tf files with no `aws_flow_log`
  resources (the "uncovered" case).
