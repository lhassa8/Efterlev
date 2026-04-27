# aws.iam_managed_via_terraform

Aggregates the customer's `aws_iam_*` resource declarations into a
summary that evidences "IAM under IaC management." Emits exactly one
Evidence per scan when any IAM resource is declared.

KSI-IAM-AAM ("Automating Account Management") asks the customer to
manage account/role/group lifecycles through automation rather than
the AWS console. A Terraform codebase declaring `aws_iam_*` resources
IS that automation — every change goes through `terraform plan` +
`terraform apply`, is reviewable, and the state file is the
authoritative record.

## What it proves

- **AC-2(2) (Automated System Account Management)** — the customer is
  managing IAM principals declaratively via IaC. Account-creation,
  role-attachment, group-membership are version-controlled rather
  than ad-hoc console operations.

## What it does NOT prove

- **Automated account-disable on suspicious activity.** AC-2(3) and
  AC-2(13) (Disable Accounts / Disable Accounts for High-Risk
  Individuals) require runtime detection + automated response —
  KSI-IAM-SUS territory.
- **Identity-proofing rigor.** IA-12 family (proofing, IDV, etc.) is
  procedural and outside what IaC can evidence.
- **Coverage across all principals.** AWS SSO / IAM Identity Center
  users, console-created users, and IAM principals declared in other
  repos are not visible to this scan. The detector reports what's in
  THIS codebase.
- **Account-lifecycle quality.** The detector reports counts, not
  whether IAM resources have appropriate permission boundaries,
  least-privilege policies, or recovery procedures. Sibling
  detectors (`aws.iam_admin_policy_usage`, `aws.iam_inline_policies_audit`)
  cover those concerns.

## KSI mapping

**KSI-IAM-AAM ("Automating Account Management").** FRMR 0.9.43-beta
lists AC-2(2), AC-2(3), AC-2(13), AC-6(7), IA-4(4), IA-12, IA-12(2),
IA-12(3), IA-12(5) in this KSI's `controls` array. This detector
evidences AC-2(2) directly. The other controls require runtime
correlation or procedural evidence.

## Output shape

Exactly one Evidence per scan when `aws_iam_*` resources exist; zero
otherwise. The Evidence is anchored at the first IAM resource's
`source_ref` for provenance walking; the content is workspace-scoped.

## Example

Input (a codebase with 3 IAM roles, 2 policies, 1 user, 4 policy attachments):

Output:

```json
{
  "detector_id": "aws.iam_managed_via_terraform",
  "ksis_evidenced": ["KSI-IAM-AAM"],
  "controls_evidenced": ["AC-2(2)"],
  "content": {
    "resource_type": "iam_managed_via_terraform",
    "resource_name": "(workspace)",
    "automation_state": "tracked",
    "iam_resource_count": 10,
    "distinct_iam_kinds": 4,
    "by_kind": {
      "role": 3,
      "policy": 2,
      "user": 1,
      "role_policy_attachment": 4
    }
  }
}
```

## Fixtures

- `fixtures/should_match/multi_iam.tf` — codebase with multiple IAM
  resource kinds → emits the summary.
- `fixtures/should_not_match/no_iam.tf` — codebase without IAM
  resources → emits nothing.
