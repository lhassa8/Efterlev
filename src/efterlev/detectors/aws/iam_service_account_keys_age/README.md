# `aws.iam_service_account_keys_age`

Inspects `aws_iam_access_key` resources, distinguishing service-account-shape keys from human-user-with-keys.

## What this detector evidences

- **KSI-IAM-SNU** (Securing Non-User Authentication).
- **800-53 controls:** IA-2, IA-5.

## What it proves

Each `aws_iam_access_key` declared in the Terraform produces one Evidence record with the user reference, a `profile_kind` (`"service_account"` if no `aws_iam_user_login_profile` is declared for the same user; `"human_user_with_keys"` if a login profile exists), and an explicit acknowledgment that key age is not visible from IaC.

## What it does NOT prove

- The key's age. Terraform doesn't carry creation timestamp or last-rotation timestamp. AWS API or CloudTrail would be needed; out of scope at v0.1.0.
- Whether the key is actually used at runtime.
- Whether the user has MFA enforced — the existing `aws.mfa_required_on_iam_policies` detector covers MFA evidence.

## Detection signal

Every `aws_iam_access_key` produces one Evidence record with a `gap` field documenting the rotation-visibility gap. The Gap Agent uses the `profile_kind` to render concerns differently — a human-user-with-keys is more often a problem than a service-account key with documented rotation procedure.

## Known limitations

- Cross-resource pairing of access keys to login profiles uses substring matching on the user reference. This is heuristic; `aws_iam_user.foo.name` and `aws_iam_user.foo` references both match `foo`, but exotic naming patterns may misclassify. Customer feedback would refine the heuristic.
- The detector is single-resource-shape; an environment with zero access keys emits zero evidence.
