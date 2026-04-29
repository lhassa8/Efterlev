# aws.iam_user_access_keys

Scans `aws_iam_access_key` resources. Emits one `Evidence` record per
declared access key, flagging it as a posture gap regardless of
whether the key is Active or Inactive — the secret material exists in
state and the presence of the declaration opts out of the
federated-identity-first pattern FedRAMP expects.

## What it proves

- **IA-2 (Identification and Authentication)** — a long-lived
  programmatic credential is declared for an IAM user.
- **AC-2 (Account Management)** — an account has an access key
  attached.
- **KSI-IAM-SNU (Securing Non-User Authentication)** — primary
  mapping. Long-lived programmatic access keys are the canonical
  insecure non-user authentication pattern. The KSI's moderate
  outcome ("Enforce appropriately secure authentication methods for
  non-user accounts and services") is direct here.
- **KSI-IAM-MFA (Enforcing Phishing-Resistant MFA)** — cross-mapping.
  Access keys bypass MFA by design (whoever holds the secret
  authenticates without an IdP challenge), so they're material
  evidence against an "MFA is enforced everywhere" claim. The
  semantic fit is weaker than the SNU primary; the cross-mapping is
  preserved per the 2026-04-29 audit (PR #90) because the underlying
  MFA-bypass concern is real.

## What it does NOT prove

- **That the key is actually used.** A declared `aws_iam_access_key`
  resource creates the credential in state even if nothing ever calls
  AWS with it. The gap is its existence; actual use is a runtime
  concern.
- **Rotation cadence.** AWS IAM does not natively rotate access keys
  on a schedule — rotation is procedural (runbooks, CI jobs, manual
  rotations). Not observable from Terraform source.
- **Whether a federated alternative is in flight.** The right fix is
  typically a migration from IAM user + access key to an IAM role
  assumed via OIDC / SAML, but we can't prove the migration is
  planned or blocked from source alone. That's manifest territory.
- **Whether the attached user also has console-login with MFA.**
  Console MFA is a separate setting; this detector only looks at the
  programmatic-credential side.

## Dogfood origin

This detector was added in response to the 2026-04-22 dogfood pass
against govnotes-demo, where ground-truth gap #8 (`ci_deploy` IAM
user with a long-lived access key for a legacy Jenkins pipeline
pre-dating the GitHub Actions OIDC migration) was completely
invisible without it. See `docs/dogfood-2026-04-22.md`.

## Example

Input:

```hcl
resource "aws_iam_user" "ci_deploy" {
  name = "ci-deploy"
}

resource "aws_iam_access_key" "ci_deploy" {
  user = aws_iam_user.ci_deploy.name
}
```

Output (one Evidence record):

```json
{
  "detector_id": "aws.iam_user_access_keys",
  "ksis_evidenced": ["KSI-IAM-SNU", "KSI-IAM-MFA"],
  "controls_evidenced": ["IA-2", "AC-2"],
  "content": {
    "resource_type": "aws_iam_access_key",
    "resource_name": "ci_deploy",
    "attached_user": "${aws_iam_user.ci_deploy.name}",
    "status": "Active",
    "gap": "long-lived programmatic access key declared; prefer IAM role with federated identity or workload assumption"
  }
}
```

## Fixtures

- `fixtures/should_match/` — access-key declarations (always flagged
  — any declared access key is a gap).
- `fixtures/should_not_match/` — .tf files with IAM users and roles
  but no `aws_iam_access_key` resources.
