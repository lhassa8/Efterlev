# aws.federated_identity_providers

Detects `aws_iam_openid_connect_provider` and `aws_iam_saml_provider`
resources. Each declared provider is evidence the customer is using
federated identity instead of long-lived AWS access keys or IAM
username/password authentication — the canonical IaC-evidenceable
signal for KSI-IAM-APM.

## What it proves

- **IA-2 (Identification and Authentication — Organizational Users)** —
  the customer has declared at least one federated provider. AWS
  principals authenticated through the provider don't use long-lived
  access keys; they exchange short-lived tokens.
- **IA-5(2) (Public Key-Based Authentication)** — fires for OIDC
  providers specifically. OIDC tokens are signed with the IdP's
  PKI; relying-party verification is PKI-based by construction.
  SAML evidence stays at IA-2 alone (SAML's XML signatures are
  different territory).

## What it does NOT prove

- **The IdP's MFA posture.** Whether the OIDC IdP itself enforces
  phishing-resistant MFA at login is KSI-IAM-MFA territory and lives
  in IdP configuration outside AWS. The detector confirms federation;
  the strength of the upstream authentication is separate.
- **Coverage across all principals.** Some IAM users may still
  authenticate with long-lived keys even when an OIDC/SAML provider
  is declared. The detector confirms the provider exists; sibling
  detectors (`aws.iam_user_access_keys`) cover the long-lived-key
  side independently.
- **Thumbprint / signing-key rotation.** IA-5(6) asks for protection
  of authenticators including key rotation. The detector reports
  thumbprint count but not rotation cadence.

## KSI mapping

**KSI-IAM-APM ("Adopting Passwordless Methods").** FRMR 0.9.43-beta
lists IA-2.1, IA-2.2, IA-2.8, IA-5.1, IA-5.2, IA-5.6, IA-6 in this
KSI's `controls` array. This detector evidences IA-2 (parent) and
IA-5(2) (Public Key-Based Authentication, OIDC only).

## Provider kinds

| `provider_kind` | Resource | Controls evidenced |
|---|---|---|
| `oidc` | `aws_iam_openid_connect_provider` | IA-2, IA-5(2) |
| `saml` | `aws_iam_saml_provider` | IA-2 (alone) |

## Common OIDC patterns

- **IRSA** (IAM Roles for Service Accounts): `url = oidc.eks.<region>.amazonaws.com/id/<id>`. Workload identity for EKS pods — the canonical
  passwordless pattern for Kubernetes workloads on AWS.
- **GitHub Actions OIDC**: `url = token.actions.githubusercontent.com`. Lets GHA workflows assume IAM roles without storing AWS keys as repo secrets.
- **GCP / Workload Identity Federation**: `url = accounts.google.com`. Cross-cloud service identity.

The detector reports the URL so the gap report can name the kind of federation in use without the customer or 3PAO having to look up the IdP separately.

## Example

Input:

```hcl
resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}
```

Output:

```json
{
  "detector_id": "aws.federated_identity_providers",
  "ksis_evidenced": ["KSI-IAM-APM"],
  "controls_evidenced": ["IA-2", "IA-5(2)"],
  "content": {
    "resource_type": "aws_iam_openid_connect_provider",
    "resource_name": "github_actions",
    "provider_kind": "oidc",
    "url": "https://token.actions.githubusercontent.com",
    "client_id_count": 1,
    "thumbprint_count": 1,
    "federation_state": "declared"
  }
}
```

## Fixtures

- `fixtures/should_match/oidc_github_actions.tf` — OIDC for GitHub Actions →
  evidences IA-2 + IA-5(2).
- `fixtures/should_match/saml_okta.tf` — SAML provider → evidences IA-2.
- `fixtures/should_not_match/no_providers.tf` — IAM user only → no evidence.
