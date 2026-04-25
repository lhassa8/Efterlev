# `aws.kms_customer_managed_keys`

Inventories declared `aws_kms_key` (customer-managed key) resources.

## What this detector evidences

- **KSI-SVC-ASM** (Automating Secret Management).
- **800-53 controls:** SC-12 (Cryptographic Key Establishment / Management).

## What it proves

Every `aws_kms_key` resource declared in the Terraform produces one Evidence record with `key_state="declared"`, capturing the description, key-usage type, deletion-window, and enable state.

## What it does NOT prove

- That the CMK is actually referenced by the resources that should use it (S3 SSE-KMS, RDS storage encryption, Secrets Manager, etc.). The Gap Agent cross-references usage against this inventory.
- That key rotation is enabled — that's the existing `aws.kms_key_rotation` detector's job.
- That key policies grant access to the right principals.

## Detection signal

Every resource of type `aws_kms_key` produces one Evidence record. AWS-managed keys (e.g., `alias/aws/s3`) are not declared as `aws_kms_key` resources in Terraform — they're auto-provisioned by AWS — so they don't appear in this detector's output by design.

## Known limitations

- Inventory-only. No cross-reference between CMK and consumer resources at the detector layer.
- Multi-region replicas (`aws_kms_replica_key`) are not currently in scope; covered separately when demand surfaces.
