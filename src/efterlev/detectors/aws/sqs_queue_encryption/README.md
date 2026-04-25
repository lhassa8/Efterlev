# `aws.sqs_queue_encryption`

Inspects `aws_sqs_queue` resources for encryption-at-rest configuration.

## What this detector evidences

- **800-53 controls:** SC-28.
- **KSI:** none — FRMR 0.9.43-beta does not map SC-28 to any KSI. Same precedent as `aws.encryption_s3_at_rest`.

## What it proves

For every declared `aws_sqs_queue`, exactly one of:
- `customer_managed` — `kms_master_key_id` references a CMK.
- `aws_managed_default` — `kms_master_key_id` is `alias/aws/sqs`.
- `sqs_managed_sse` — `sqs_managed_sse_enabled = true` (the SSE-SQS path AWS introduced as a simpler alternative).
- `absent` — neither set; messages are not encrypted at rest. Emits a gap message.

## What it does NOT prove

- That producers and consumers handle messages securely after dequeue.
- That messages are encrypted in transit (SC-8).
- That the queue's access policy enforces appropriate auth.

## Detection signal

Every `aws_sqs_queue` produces one Evidence record. Only the `absent` case includes a `gap` field — the rest are inventory-shape evidence the Gap Agent contextualizes.

## Known limitations

- The detector does not cross-reference the CMK's own key policy.
- A queue with `kms_master_key_id` set to `alias/aws/sqs` is functionally equivalent to `sqs_managed_sse_enabled = true` for SC-28 purposes; we report them as distinct states so the Gap Agent can render the literal config faithfully.
