# aws.encryption_ebs

Detects EBS volume at-rest encryption across two patterns: standalone
`aws_ebs_volume` resources and inline `root_block_device` /
`ebs_block_device` blocks on `aws_instance` resources. Emits one
`Evidence` record per volume or block.

## What it proves

- **SC-28 (Protection of Information at Rest)** — an EBS volume has
  (or does not have) at-rest encryption declared in Terraform.
- **SC-28(1) (Cryptographic Protection)** — when encryption is
  enabled, evidence that AWS's default AES-256 algorithm is in use
  (AWS does not expose a choice of algorithm for EBS at-rest
  encryption).

When `kms_key_id` is set, `key_management=customer_managed` is
recorded for cross-referencing with the `kms_key_rotation` detector.

## What it does NOT prove

- **Key rotation.** SC-12 territory — that's the `kms_key_rotation`
  detector's job.
- **BYOK / HSM-backed key material.** Operational concerns beyond
  what Terraform declares.
- **Snapshot-encryption inheritance.** Snapshots of encrypted
  volumes are automatically encrypted, but manually-created
  snapshots of later attachments may differ — out of scope here.
- **Runtime state.** Console changes that toggled encryption after
  `terraform apply` are invisible.

## Inline block handling

An `aws_instance` can declare an inline `root_block_device` (at most
one) and multiple `ebs_block_device` blocks. Each is emitted as its
own Evidence record with `location` indicating which kind and
`resource_name` of the form `<instance>.root_block_device` or
`<instance>.ebs_block_device[<index>]` so the Gap Agent can cite per
block.

## KSI mapping

**None.** Same rationale as `encryption_s3_at_rest` and
`rds_encryption_at_rest`: FRMR 0.9.43-beta lists no KSI with SC-28
in its `controls` array. Per DECISIONS 2026-04-21 design call #1
(Option C), the detector declares `ksis=[]` and the Gap Agent renders
findings at the 800-53 (SC-28) level only.

## Example

Input:

```hcl
resource "aws_ebs_volume" "app_data" {
  availability_zone = "us-east-1a"
  size              = 100
  encrypted         = true
  kms_key_id        = "arn:aws:kms:us-east-1:123:key/abc-123"
}

resource "aws_instance" "bastion" {
  ami           = "ami-abc"
  instance_type = "t3.micro"

  root_block_device {
    volume_size = 20
    encrypted   = true
    kms_key_id  = "arn:aws:kms:us-east-1:123:key/abc-123"
  }
}
```

Output (two Evidence records):

```json
[
  {
    "detector_id": "aws.encryption_ebs",
    "controls_evidenced": ["SC-28", "SC-28(1)"],
    "content": {
      "resource_type": "aws_ebs_volume",
      "resource_name": "app_data",
      "location": "standalone",
      "encryption_state": "present",
      "algorithm": "AES256",
      "key_management": "customer_managed",
      "kms_key_id": "arn:aws:kms:us-east-1:123:key/abc-123"
    }
  },
  {
    "detector_id": "aws.encryption_ebs",
    "controls_evidenced": ["SC-28", "SC-28(1)"],
    "content": {
      "resource_type": "aws_instance",
      "resource_name": "bastion.root_block_device",
      "location": "root_block_device",
      "encryption_state": "present",
      "algorithm": "AES256",
      "key_management": "customer_managed",
      "kms_key_id": "arn:aws:kms:us-east-1:123:key/abc-123"
    }
  }
]
```

## Fixtures

- `fixtures/should_match/` — volumes (standalone and inline) with
  `encrypted = true`.
- `fixtures/should_not_match/` — explicitly unencrypted volumes, and
  .tf files with no EBS-shaped resources.
