# aws.s3_lifecycle_policies

Detects `aws_s3_bucket_lifecycle_configuration` resources and reports
whether each configuration includes rules that expire or transition
objects. KSI-SVC-RUD ("Removing Unwanted Data") asks the customer to
remove unwanted data on a defined cadence — S3 lifecycle policies are
the canonical IaC-evidenceable signal at the storage layer.

## What it proves

- **SI-12 (Information Management and Retention)** — the customer
  declares a lifecycle configuration, providing structural evidence of
  data-retention discipline.
- **SI-12(3) (Destruction)** — fires when at least one enabled rule
  contains an `expiration` block (delete-after-N pattern). Pure
  storage-class transitions (e.g. `STANDARD_IA` → `GLACIER`) do NOT
  evidence SI-12(3); they reduce cost but do not destroy data.

## What it does NOT prove

- **That the retention period matches policy.** "Delete after 7 days"
  vs "Delete after 7 years" are wildly different commitments — the
  detector reports presence, not adequacy. Per-organization risk
  decision.
- **That lifecycle actions actually run.** AWS executes lifecycle
  rules asynchronously and within a few days of the threshold; the
  detector confirms the rule is declared, not that it fires.
- **That PII is identified before deletion.** SI-18(4) (PII Quality
  Operations — Updates) is adjacent and not directly evidenced.
  Tagging or classification of objects before deletion is procedural.
- **Other storage backends.** RDS automated-backup retention, EBS
  snapshot lifecycles, and DynamoDB TTL configurations cover other
  storage classes and remain candidates for sibling detectors.

## KSI mapping

**KSI-SVC-RUD ("Removing Unwanted Data").** FRMR 0.9.43-beta lists
SI-12(3) and SI-18(4) in this KSI's `controls` array. This detector
evidences SI-12 (parent) and SI-12(3) (destruction) when expiration
rules are present.

## Lifecycle states

| State | Meaning | Controls evidenced |
|---|---|---|
| `configured_with_expiration` | ≥1 enabled rule with expiration block | SI-12, SI-12(3) |
| `configured_no_expiration` | rules enabled but no expirations (transitions only) | SI-12 (with gap) |
| `placeholder` | config declared, no enabled action rules | SI-12 (with gap) |

`configured_no_expiration` and `placeholder` Evidence carries a `gap`
field naming what's missing.

## Rule status interpretation

A rule is **enabled** when `status="Enabled"` or `status` is omitted
(the AWS default). `status="Disabled"` rules are present but inactive —
the detector counts them in `rule_count` but not `enabled_rule_count`.

## Example

Input:

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit.id

  rule {
    id     = "expire_after_year"
    status = "Enabled"

    expiration {
      days = 365
    }
  }

  rule {
    id     = "transition_to_glacier"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}
```

Output:

```json
{
  "detector_id": "aws.s3_lifecycle_policies",
  "ksis_evidenced": ["KSI-SVC-RUD"],
  "controls_evidenced": ["SI-12", "SI-12(3)"],
  "content": {
    "resource_type": "aws_s3_bucket_lifecycle_configuration",
    "resource_name": "audit_logs",
    "bucket_ref": "${aws_s3_bucket.audit.id}",
    "rule_count": 2,
    "enabled_rule_count": 2,
    "expiration_rule_count": 1,
    "transition_rule_count": 1,
    "lifecycle_state": "configured_with_expiration"
  }
}
```

## Fixtures

- `fixtures/should_match/with_expiration.tf` — config with both
  expiration and transition rules → `configured_with_expiration`.
- `fixtures/should_not_match/transitions_only.tf` — only transition
  rules → `configured_no_expiration` with gap.
- `fixtures/should_not_match/disabled_only.tf` — rule declared but
  status=Disabled → `placeholder` with gap.
