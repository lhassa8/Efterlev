# `aws.elb_access_logs`

Inspects Application/Network/Classic load-balancer access-log configuration.

## What this detector evidences

- **KSI-MLA-LET** (Logging Event Types).
- **800-53 controls:** AU-2 (Event Logging), AU-12 (Audit Record Generation).

## What it proves

For every `aws_lb`, `aws_alb`, or `aws_elb` resource, one Evidence record is emitted with `log_state` set to:

- `enabled` — `access_logs.bucket` is set; `enabled` is true (or absent — AWS default treats bucket-set as enabled).
- `bucket_only` — bucket configured but `enabled = false`.
- `absent` — no `access_logs` block at all.

## What it does NOT prove

- That the destination S3 bucket is itself encrypted (separate detector: `aws.encryption_s3_at_rest`).
- That the bucket has retention/lifecycle policies appropriate for log evidence.
- That anyone actually reads the logs.

## Detection signal

Each load-balancer resource produces exactly one Evidence record. The `gap` field populates only on the `absent` state — `bucket_only` is informational, not finding-shape, since the operator may have temporarily disabled logging for a known reason.

## Known limitations

- Modern ALBs and NLBs use `aws_lb` (the `aws_alb` alias is legacy but still valid). The detector treats both as `lb_kind = "alb_or_nlb"`.
- Classic ELBs are inspected via `aws_elb`. Few new workloads use classic ELBs; included for completeness.
- Connection logs (a separate AWS feature) and execution logs (Lambda integration) are out of scope; this detector covers access logs only.
