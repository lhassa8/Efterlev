# aws.rds_encryption_at_rest

Detects whether an `aws_db_instance` declares `storage_encrypted = true`
and, when it does, whether a customer-managed KMS key is bound. Emits
one `Evidence` record per RDS instance.

## What it proves

- **SC-28 (Protection of Information at Rest)** — an RDS instance has (or
  does not have) at-rest storage encryption declared in Terraform.
- **SC-28(1) (Cryptographic Protection)** — when encryption is enabled,
  evidence that AWS's default AES-256 algorithm is in use. AWS does not
  expose a choice of algorithm for RDS at-rest encryption; `storage_encrypted=true`
  implies AES-256.

Additionally, when `kms_key_id` is set, `key_management=customer_managed`
is recorded for cross-referencing with the `kms_key_rotation` detector's
output.

## What it does NOT prove

- **Key rotation, BYOK, customer-key governance.** SC-12 territory —
  that's the `kms_key_rotation` detector's job (rotation evidence) and
  remains procedural beyond what Terraform shows (KMS-external HSM,
  key-escrow, etc.).
- **Snapshot encryption.** RDS snapshots have their own encryption
  semantics (inherited at snapshot creation for encrypted instances but
  configurable via `copy_tags_to_snapshot` and separate snapshot
  resources). Not examined here.
- **Read-replica encryption.** Cross-region replicas can have different
  keys; the detector emits facts per-primary-instance only.
- **Runtime state.** Deployed databases may differ from what Terraform
  declares (manual console changes, drift); only the declaration is
  examined.

## KSI mapping

**None.** Same rationale as `encryption_s3_at_rest`: FRMR 0.9.43-beta
lists no KSI whose `controls` array contains SC-28. Per DECISIONS
2026-04-21 design call #1 (Option C), the detector declares `ksis=[]`
and the Gap Agent renders findings as "unmapped to any current KSI."

## Example

Input:

```hcl
resource "aws_db_instance" "primary" {
  identifier        = "app-primary"
  engine            = "postgres"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_encrypted = true
  kms_key_id        = "arn:aws:kms:us-east-1:123:key/abc-123"
}
```

Output:

```json
{
  "detector_id": "aws.rds_encryption_at_rest",
  "ksis_evidenced": [],
  "controls_evidenced": ["SC-28", "SC-28(1)"],
  "content": {
    "resource_type": "aws_db_instance",
    "resource_name": "primary",
    "encryption_state": "present",
    "algorithm": "AES256",
    "key_management": "customer_managed",
    "kms_key_id": "arn:aws:kms:us-east-1:123:key/abc-123"
  }
}
```

## Fixtures

- `fixtures/should_match/` — RDS instances with `storage_encrypted=true`.
- `fixtures/should_not_match/` — RDS instances with encryption omitted or
  explicitly false, and .tf files with no `aws_db_instance` resources.
