# aws.kms_key_rotation

Detects `aws_kms_key` resources and reports whether automatic key
rotation is enabled. Accounts for asymmetric CMKs, which do not support
automatic rotation (AWS ignores `enable_key_rotation` on those).

## What it proves

- **SC-12 (Cryptographic Key Establishment and Management)** — a KMS
  customer master key is declared in Terraform and its rotation posture
  is visible. For symmetric CMKs, `enable_key_rotation=true` records
  `rotation_status=enabled`; absent or `false` records `disabled`.
- **SC-12(2) (Symmetric Keys)** — specifically, when a symmetric CMK is
  confirmed to be on AWS's automatic rotation schedule.

## What it does NOT prove

- **HSM-backed or BYOK key material.** The `origin` attribute on
  `aws_kms_key` can name AWS_CLOUDHSM, EXTERNAL, etc. This detector
  does not branch on `origin`; that is a separate concern (key escrow
  and custody are SC-12(3) and procedural).
- **Multi-region key replication and replica key handling.**
- **Whether applications actually use the declared CMK** vs. falling
  through to AWS-managed keys (`alias/aws/s3`, etc.). That requires
  cross-referencing IAM policies and service-specific configuration.
- **Operational custody.** Personnel controls on who can
  `DisableKeyRotation`, `ScheduleKeyDeletion`, etc. — procedural.
- **Runtime state.** Deployed keys may have been modified via the
  console; only the Terraform declaration is examined.

## KSI mapping

**KSI-SVC-ASM ("Automating Secret Management").** FRMR 0.9.43-beta
includes SC-12 in this KSI's `controls` array, and the KSI statement
explicitly names "rotation of digital keys, certificates, and other
secrets" — KMS key rotation is the canonical example. The 2026-04-21
design call originally left this `ksis=[]` under the assumption that
no clean mapping existed; the 2026-04-27 honesty pass re-evaluated and
confirmed KSI-SVC-ASM is the right home. KSI-SVC-VRI was considered but its
controls center on SC-13 (cryptographic integrity), not SC-12 (key
management lifecycle).

## Asymmetric keys

`customer_master_key_spec` values starting with `RSA_`, `ECC_`, `HMAC_`,
or `SM2` describe asymmetric keys. AWS ignores `enable_key_rotation` on
these. The detector records `rotation_status=not_applicable` with a
`note` so the Gap Agent does not treat asymmetric keys as rotation gaps.

## Example

Input:

```hcl
resource "aws_kms_key" "app_data" {
  description             = "Application-data encryption key"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}
```

Output:

```json
{
  "detector_id": "aws.kms_key_rotation",
  "ksis_evidenced": ["KSI-SVC-ASM"],
  "controls_evidenced": ["SC-12", "SC-12(2)"],
  "content": {
    "resource_type": "aws_kms_key",
    "resource_name": "app_data",
    "rotation_status": "enabled"
  }
}
```

## Fixtures

- `fixtures/should_match/` — symmetric CMKs with rotation enabled.
- `fixtures/should_not_match/` — symmetric CMKs with rotation off, an
  asymmetric CMK (rotation_not_applicable), and .tf files with no KMS
  resources.
