# `aws.s3_bucket_public_acl`

Flags S3 bucket ACLs and bucket policies that expose the bucket to anonymous access.

## What this detector evidences

- **KSI-CNA-RNT** (Restricting Network Traffic) and **KSI-CNA-MAT** (Minimizing Attack Surface).
- **800-53 controls:** AC-3, SC-7.

## What it proves

One of:
- An `aws_s3_bucket_acl` resource has `acl` set to `public-read` or `public-read-write`.
- An `aws_s3_bucket_policy` resource has at least one `Statement` with `Effect = "Allow"` and `Principal = "*"` (or `{"AWS": "*"}`).

## What it does NOT prove

- That the bucket actually contains anything sensitive.
- That an `aws_s3_bucket_public_access_block` resource isn't overriding the ACL/policy. PAB does override; this detector still surfaces the declared intent because operator intent is itself worth flagging.
- The full set of cross-account access paths a more sophisticated bucket policy might enable.

## Detection signal

- Public canned ACL → `exposure_state="public_acl"` evidence.
- Bucket policy granting `Allow` to anonymous → `exposure_state="anonymous_allow"` evidence.
- Policy built via `jsonencode(...)` or `data.aws_iam_policy_document.X.json` → `exposure_state="unparseable"` evidence (the policy body renders as `${...}` from HCL parsing alone).

## Known limitations

- Heredoc-style literal JSON policies are parsed; everything else is unparseable. This is a known IaC limitation that the existing `aws.mfa_required_on_iam_policies` detector also documents.
- The detector is single-resource-shaped. Cross-resource analysis ("does the PAB attached to this bucket override its public ACL?") is Gap Agent territory.
