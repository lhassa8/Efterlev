# `aws.iam_inline_policies_audit`

Inventories inline-policy resources attached to IAM principals.

## What this detector evidences

- **KSI-IAM-ELP** (Ensuring Least Privilege).
- **KSI-IAM-JIT** (Authorizing Just-in-Time) — cross-mapped via both AC-2 and AC-6, which appear in KSI-IAM-JIT's FRMR `controls` array. Inline policies on principals are the standing-grant antithesis of just-in-time authorization.
- **800-53 controls:** AC-2, AC-6.

## What it proves

Each `aws_iam_role_policy`, `aws_iam_user_policy`, and `aws_iam_group_policy` resource is inventoried. These are inline policies — they attach permissions directly to a single role/user/group rather than via a managed policy that can be shared and reviewed centrally.

## What it does NOT prove

- That the policy itself grants over-broad permissions. Policy bodies built via `jsonencode(...)` or `data.aws_iam_policy_document.X.json` render as `${...}` placeholders from HCL alone; the detector flags policy_state as `unparseable` in that case.
- That inline use is incorrect for this case — there are legitimate reasons to use inline (tightly-scoped, single-purpose attachments to a role unique to one workload). The detector is informational, not finding-shape; the Gap Agent decides.

## Detection signal

Each matching resource produces one Evidence record. There is no negative-emit; an environment using only managed policies emits zero evidence here, which is the "good shape."

## Known limitations

- Policy-content evaluation is out of scope. The MFA detector (`aws.mfa_required_on_iam_policies`) handles literal-JSON policy parsing for one specific concern; this detector intentionally doesn't duplicate that.
