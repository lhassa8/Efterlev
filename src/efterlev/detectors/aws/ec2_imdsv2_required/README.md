# `aws.ec2_imdsv2_required`

Inspects every `aws_instance` and `aws_launch_template` and reports whether IMDSv2 is enforced via `metadata_options.http_tokens = "required"`.

## What this detector evidences

- **KSI-CNA-IBP** (Implementing Best Practices).
- **800-53 controls:** CM-2 (Baseline Configuration).

## What it proves

For each EC2 instance or launch template, the detector reads `metadata_options.http_tokens`:

- `"required"` — IMDSv2-only, the AWS-recommended baseline.
- `"optional"` — IMDSv1 is reachable. Gap.
- absent — AWS default allows both IMDSv1 and IMDSv2. Gap.

One Evidence is emitted per resource with `imds_state` ∈ `{imdsv2_required, imdsv1_allowed, metadata_options_unset, unknown}`.

## Why this matters

EC2's instance metadata service (IMDS) lets workloads on the instance ask for credentials, region, and IAM-role tokens. IMDSv1 accepts unauthenticated GETs from the workload — which means an SSRF in the workload (Capital One's basis) reaches the metadata service and exfiltrates the IAM role's credentials. IMDSv2 fixes this by requiring a session token (PUT to `/latest/api/token`); SSRF tools that don't support PUT are stymied.

Every serious AWS hardening guide flags non-IMDSv2 instances as a finding. The IaC-evidenceable signal is exactly `http_tokens = "required"` in the `metadata_options` block.

## What it does NOT prove

- That all EC2 instances in the boundary are covered by these Terraform resources. A console-launched instance won't be flagged here; AWS Config rule `ec2-imdsv2-check` covers that gap at runtime.
- That runtime drift hasn't reverted the setting. The Terraform state is the source of truth for IaC; runtime is its own surface.
- That the `http_put_response_hop_limit` is appropriate for the workload (containers may need 2 instead of the default 1). The detector reports the value but doesn't classify on it.

## Detection signal

One Evidence record per matching resource. The `gap` field populates whenever `imds_state ∈ {imdsv1_allowed, metadata_options_unset}` — `imdsv2_required` and `unknown` (interpolated value) do not populate gap.

## Known limitations

- `aws_launch_configuration` is not covered. Launch configurations are deprecated in favor of launch templates; if a customer is still using them, they have a different baseline-configuration issue worth surfacing separately.
- `aws_autoscaling_group` resources reference launch templates by ID — the detector does not chase the reference; the launch-template resource itself is what we examine.
