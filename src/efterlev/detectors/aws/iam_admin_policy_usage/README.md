# `aws.iam_admin_policy_usage`

Flags every IAM principal with the AWS-managed `AdministratorAccess` policy attached.

## What this detector evidences

- **KSI-IAM-ELP** (Ensuring Least Privilege).
- **800-53 controls:** AC-6, AC-6(2).

## What it proves

For each `aws_iam_{role,user,group}_policy_attachment` resource where `policy_arn == "arn:aws:iam::aws:policy/AdministratorAccess"`, one Evidence record is emitted naming the principal.

## What it does NOT prove

- That the privilege is unjustified — emergency break-glass roles, deployment automation roles, and organization-admin roles legitimately have it.
- That the principal is actually used at runtime; CloudTrail analysis would be needed.
- That the principal has additional restrictions imposed by service-control policies, permission boundaries, or session-policy at assumption time.

## Detection signal

One Evidence record per matching attachment. The `gap` field always populates — the Gap Agent decides whether each is a real concern based on principal naming, surrounding context, and customer-supplied manifest attestations.

## Known limitations

- AWS-managed `AdministratorAccess` is the only policy this detector matches by ARN. Other broadly-permissive AWS-managed policies (e.g., `PowerUserAccess`) are not flagged. If customer feedback identifies a specific list, add them or build a per-policy-ARN allowlist mechanism.
- Customer-managed policies that grant `*:*` aren't flagged — those would require parsing the policy document, which the existing `aws.mfa_required_on_iam_policies` detector handles for its scope. Building a generic "policy is overly broad" detector is a larger design effort.
