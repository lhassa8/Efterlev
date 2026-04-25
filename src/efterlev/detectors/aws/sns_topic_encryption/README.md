# `aws.sns_topic_encryption`

Inspects `aws_sns_topic` resources for KMS-key-based encryption-at-rest configuration.

## What this detector evidences

- **800-53 controls:** SC-28 (Protection of Information at Rest).
- **KSI:** none — FRMR 0.9.43-beta does not map SC-28 to any KSI. Same precedent as `aws.encryption_s3_at_rest`. The Gap Agent renders SC-28 evidence under "unmapped findings."

## What it proves

For every declared `aws_sns_topic`, evidence is emitted distinguishing:
- `customer_managed` — `kms_master_key_id` references a CMK (the strong-encryption case).
- `aws_managed_default` — attribute is set to `alias/aws/sns`, OR the attribute is absent (AWS encrypts with the default service key automatically).

## What it does NOT prove

- That subscribers' downstream message handling preserves confidentiality.
- That messages are encrypted in transit (separate control: SC-8).
- That the CMK referenced has a sensible key policy.

## Detection signal

Every `aws_sns_topic` produces one Evidence record. The `encryption_state` value distinguishes the three cases. There is no negative-emit; encryption is always at least AWS-managed default for SNS.

## Known limitations

- The detector inspects each topic in isolation. Whether the CMK is itself rotated and managed correctly is the existing `aws.kms_key_rotation` and `aws.kms_customer_managed_keys` detectors' responsibility.
