# Deploying Efterlev in AWS GovCloud EC2

This walkthrough takes you from "empty AWS GovCloud account" to "working `efterlev agent gap` run against your Terraform" — without any traffic leaving the GovCloud boundary. The only outbound network call from a configured Efterlev run is the LLM inference, which on this deployment goes to the regional Bedrock endpoint inside GovCloud.

A reproducibility note up front: every command in this doc has been tested in spirit (all the AWS, EC2, and Bedrock primitives behave as documented in their AWS docs as of April 2026), but the maintainer has not yet walked the full sequence end-to-end on a fresh GovCloud account. The acceptance proof is `EFTERLEV_BEDROCK_SMOKE=1 uv run python scripts/e2e_smoke.py --llm-backend bedrock --llm-region us-gov-west-1` succeeding on a GovCloud EC2 instance configured per this doc — see [SPEC-13](specs/SPEC-13.md). Until that landing, treat the doc as authoritative-with-a-stamp-pending.

## 1. When to use this deployment

You should be reading this if:

- You have a FedRAMP-authorized AWS GovCloud account, or you're standing one up as part of a FedRAMP 20x Moderate authorization effort.
- You want Efterlev to scan the Terraform for that GovCloud-deployed system from inside the same boundary, so no metadata about your evidence — even content-hashed — crosses to the commercial internet.
- You're comfortable with EC2, IAM, and VPC fundamentals. This is not a Cloud-101 doc.

If you don't have a GovCloud account yet, run Efterlev from a developer laptop or commercial-AWS CI runner instead. Most of the value lands without the GovCloud-specific deployment step. See the main [README](../README.md) install section.

## 2. What Efterlev does and does not phone home

The scanner is fully local. The detector library, manifest loader, FRMR parser, and provenance store make zero outbound calls. The HTML and FRMR-attestation-JSON renderers don't either.

The only outbound traffic from a configured Efterlev run is the LLM inference for the three agents (Gap, Documentation, Remediation). With `backend = "bedrock"` (SPEC-11) and a GovCloud region, that traffic goes to `bedrock-runtime.us-gov-west-1.amazonaws.com` (or `.us-gov-east-1.amazonaws.com`), which is inside the FedRAMP-authorized boundary.

Efterlev never:
- Phones home for telemetry or analytics.
- Publishes scan results or evidence to any third-party service.
- Writes content outside `.efterlev/` and the explicitly-named report output directory.
- Persists secrets — secret-shaped substrings are scrubbed from prompts before egress (see `THREAT_MODEL.md`).

## 3. Prerequisites

You'll need:

- An AWS GovCloud account (separate from your commercial AWS account; sign-up flow at https://aws.amazon.com/govcloud-us/getting-started/).
- IAM admin in that account for the setup steps (you can hand off to your platform team after).
- Amazon Bedrock model access enabled in the target GovCloud region. Request via the Bedrock console under **Model access** → **Manage model access** → check the Anthropic Claude model(s) you want.
- A choice of EC2 instance:
  - Interactive use / one-off scans: `t3.medium` or `t3.large` is plenty.
  - CI runner with parallel scans: `c6i.xlarge` or larger.
  - **No GPU required.** Efterlev does no local inference; everything inference-y runs on Bedrock.
- A VPC with private subnets in the target region (or you can create one as part of step 2).
- An existing Terraform codebase you want to scan, accessible from the EC2 instance (clone, mount, or rsync — your call).

## 4. Step 1: IAM policy for Bedrock invocation

Create a least-privilege IAM policy that grants only what the AnthropicBedrockClient needs. Save as `efterlev-bedrock-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeBedrockClaudeModels",
      "Effect": "Allow",
      "Action": [
        "bedrock:Converse",
        "bedrock:InvokeModel"
      ],
      "Resource": [
        "arn:aws-us-gov:bedrock:us-gov-west-1::foundation-model/us.anthropic.claude-opus-4-7-v1:0",
        "arn:aws-us-gov:bedrock:us-gov-west-1::foundation-model/us.anthropic.claude-sonnet-4-6-v1:0"
      ]
    }
  ]
}
```

Two things worth flagging:

- **Resource ARN partition is `aws-us-gov`**, not `aws`. GovCloud uses a separate partition; the `aws` partition ARNs you see in commercial-AWS docs do not apply.
- **Scope to specific model ARNs.** The example above lists the primary model and the fallback model from a typical `efterlev init --llm-backend bedrock` config. Add or remove model ARNs to match what your config actually pins. A wildcard (`arn:aws-us-gov:bedrock:us-gov-west-1::foundation-model/*`) works but is sloppier.

Apply:

```bash
aws --region us-gov-west-1 iam create-policy \
  --policy-name efterlev-bedrock-policy \
  --policy-document file://efterlev-bedrock-policy.json

aws --region us-gov-west-1 iam create-role \
  --role-name efterlev-ec2-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws --region us-gov-west-1 iam attach-role-policy \
  --role-name efterlev-ec2-role \
  --policy-arn arn:aws-us-gov:iam::<your-account-id>:policy/efterlev-bedrock-policy

aws --region us-gov-west-1 iam create-instance-profile \
  --instance-profile-name efterlev-ec2-profile

aws --region us-gov-west-1 iam add-role-to-instance-profile \
  --instance-profile-name efterlev-ec2-profile \
  --role-name efterlev-ec2-role
```

The instance profile is what you'll attach to the EC2 instance in step 3.

## 5. Step 2: VPC endpoint for Bedrock

Create an interface VPC endpoint so Bedrock traffic stays on the AWS network and never hits public DNS resolution:

```bash
aws --region us-gov-west-1 ec2 create-vpc-endpoint \
  --vpc-id vpc-<your-vpc-id> \
  --vpc-endpoint-type Interface \
  --service-name com.amazonaws.us-gov-west-1.bedrock-runtime \
  --subnet-ids subnet-<your-private-subnet-id> \
  --security-group-ids sg-<your-vpc-endpoint-sg> \
  --private-dns-enabled
```

`--private-dns-enabled` is the load-bearing flag: with it on, AWS resolves `bedrock-runtime.us-gov-west-1.amazonaws.com` to the VPC endpoint's IP for resources inside the VPC. Without it, you'd need to point your client at the endpoint's specific DNS name, which leaks implementation details into your config.

The security group `sg-<your-vpc-endpoint-sg>` should permit HTTPS (port 443) ingress from the EC2 instance's security group. Nothing else.

## 6. Step 3: Launch the EC2 instance

Use Amazon Linux 2023 (or RHEL 9 / Ubuntu 22.04 LTS — any Linux with Docker available works for the container path):

```bash
aws --region us-gov-west-1 ec2 run-instances \
  --image-id ami-<amazon-linux-2023-ami-in-govcloud> \
  --instance-type t3.medium \
  --key-name <your-key-pair> \
  --iam-instance-profile Name=efterlev-ec2-profile \
  --subnet-id subnet-<your-private-subnet-id> \
  --security-group-ids sg-<ec2-instance-sg> \
  --metadata-options "HttpTokens=required" \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=efterlev-scan}]'
```

`HttpTokens=required` enforces IMDSv2, which is required for the instance profile credentials path Efterlev's boto3 client will use.

SSH in and install Efterlev. Two options:

**Option A: container (recommended for GovCloud)** — pulls a pre-built image with boto3 baked in. Air-gap-friendly since you can mirror this image into your private registry once.

```bash
sudo yum install -y docker
sudo systemctl enable --now docker
sudo usermod -a -G docker ec2-user
# log out and back in for the group change to take effect

docker pull ghcr.io/efterlev/efterlev:latest
```

**Option B: pipx with the bedrock extra** — installs the Python package directly. Lighter; needs Python 3.12+.

```bash
sudo yum install -y python3.12 pipx
pipx install 'efterlev[bedrock]'
```

(Adjust package names for RHEL 9 / Ubuntu / your distro; see your distro's instructions for getting Python 3.12.)

## 7. Step 4: Configure Efterlev

`cd` into the directory holding the Terraform you want to scan (clone, mount, or rsync first; out of scope for this doc). Then:

```bash
efterlev init \
  --llm-backend bedrock \
  --llm-region us-gov-west-1 \
  --llm-model us.anthropic.claude-opus-4-7-v1:0 \
  --baseline fedramp-20x-moderate
```

(Container variant: `docker run --rm -v $(pwd):/repo ghcr.io/efterlev/efterlev:latest init --llm-backend bedrock --llm-region us-gov-west-1 ...`.)

The resulting `.efterlev/config.toml` will look like:

```toml
[llm]
backend = "bedrock"
model = "us.anthropic.claude-opus-4-7-v1:0"
fallback_model = "claude-sonnet-4-6"
region = "us-gov-west-1"

[scan]
target_dir = "."
output_dir = "./out"

[baseline]
id = "fedramp-20x-moderate"
```

Notice that `fallback_model` defaults to a commercial-region model name. For a GovCloud-only deployment you'll want to update it manually to the GovCloud model ID:

```toml
fallback_model = "us.anthropic.claude-sonnet-4-6-v1:0"
```

(A future version of `efterlev init` may auto-set this when `--llm-backend=bedrock`; for now the CLI's `--llm-backend` flag groups don't include a `--llm-fallback-model` flag. Tracked as a small follow-up.)

## 8. Step 5: Verify no-egress

This is the test that the boundary is being held.

Add an egress rule to your EC2 security group that *blocks* traffic to `anthropic.com` (or use a network ACL). The crude version: deny all outbound except 443 to the Bedrock endpoint's prefix list. The targeted version:

```bash
# Block outbound HTTPS to anything not in the GovCloud Bedrock prefix list.
# (Specifics depend on your VPC topology; consult your security team's baseline.)
```

Then run:

```bash
efterlev agent gap --target .
```

It should succeed: scan finds evidence, gap-classification request goes to Bedrock via the VPC endpoint, response comes back, classification HTML lands in `.efterlev/reports/`. If any `anthropic.com` resolution attempt is made, the security group blocks it and the run fails with a clear error.

The automated equivalent is `scripts/e2e_smoke.py --llm-backend bedrock --llm-region us-gov-west-1` from the Efterlev source tree, which runs the full agent pipeline and asserts every check passes (SPEC-13).

## 9. Step 6: Run against your Terraform

Once steps 1–5 are working, the everyday flow is:

```bash
efterlev scan --target .
efterlev agent gap --target .
efterlev agent document --target .
efterlev agent remediate --ksi KSI-SVC-SNT --target .
```

Reports land in `.efterlev/reports/` as self-contained HTML. The FRMR-attestation JSON from `agent document` lands as `attestation-<timestamp>.json` in the same directory.

## 10. Cost profile

Bedrock pricing differs from Anthropic-direct pricing. Per-token rates vary by model and change over time, so we don't reproduce numbers here that would go stale fast.

What to budget for:
- A full FedRAMP Moderate Gap-Agent run touches the model with each KSI's evidence set in context. ~60 KSIs × prompt+response per KSI. At Opus rates, this is on the order of several US dollars per run; at Sonnet rates, roughly 1/5 that.
- Documentation and Remediation agents are similar order-of-magnitude per invocation.
- Over a day of active use during a FedRAMP push, the LLM bill is typically tens to low-hundreds of dollars on Opus. Compare against Anthropic-direct rates on your existing account; the multiplier is meaningful but not dramatic.

For exact rates: AWS Bedrock pricing page → us-gov-west-1 tab → Anthropic models. Refresh before budgeting.

## 11. Troubleshooting

### `AccessDeniedException` on the first agent call

Usually means Bedrock model access is not yet granted in your account, or the IAM policy's resource ARNs don't match the model ID in your config.

Fix:
1. Check the Bedrock console → Model access → confirm the requested Anthropic Claude model is **Granted** (not Pending or Available).
2. Compare the model ID in `.efterlev/config.toml` against the resource ARNs in `efterlev-bedrock-policy.json`. They must match exactly, including the `aws-us-gov` partition.

### `ResourceNotFoundException`

Means the model ID is not available in the requested region. AnthropicBedrockClient treats this as non-retryable, so it surfaces immediately.

Fix:
1. Check the model ID syntax. GovCloud uses the same `us.anthropic.claude-...-v1:0` namespace as US commercial Bedrock for cross-region inference profiles.
2. Try a different model that is GovCloud-available; the AWS docs maintain the canonical list.

### Bedrock VPC endpoint DNS not resolving

Symptom: `efterlev agent gap` fails with `EndpointConnectionError: Could not connect to the endpoint URL`. Means the VPC endpoint isn't routing traffic for `bedrock-runtime.us-gov-west-1.amazonaws.com`.

Fix:
1. Check the VPC endpoint state — should be `available`.
2. Confirm `--private-dns-enabled` is on.
3. Confirm the EC2 instance's subnet is in the same VPC as the endpoint.
4. Confirm the security group on the VPC endpoint allows HTTPS ingress from the EC2 security group.

### `EXPIRED_TOKEN` or credential errors

Usually means the EC2 instance is using IMDSv1 instead of IMDSv2, or the instance profile didn't get attached at launch time.

Fix:
1. `aws sts get-caller-identity` from the EC2 instance — should return the role's ARN.
2. If not, check the instance description: `aws ec2 describe-instances --instance-ids <id>` should show the IamInstanceProfile.
3. Check IMDS metadata options — `HttpTokens=required` (per step 3 above) requires the AWS SDK to use IMDSv2. boto3 1.35+ does this by default.

### Smoke test still hits anthropic.com

Symptom: you blocked egress per step 5 but the agent commands still work.

Fix:
1. Check `.efterlev/config.toml` — `backend` must be `"bedrock"`. If it's `"anthropic"`, the run is going to the Anthropic API, which the security group might be allowing because of an unintended egress rule.
2. Re-run `efterlev init --force --llm-backend bedrock --llm-region us-gov-west-1 ...` to overwrite.

## 12. Further reading

- [SPEC-10](specs/SPEC-10.md) — the AnthropicBedrockClient implementation.
- [SPEC-11](specs/SPEC-11.md) — the `LLMConfig.backend` / `region` config surface.
- [SPEC-13](specs/SPEC-13.md) — the e2e smoke harness's Bedrock path; the canonical "did this deployment actually work?" check.
- [THREAT_MODEL.md](../THREAT_MODEL.md) — what Efterlev's egress and secret-handling guarantees actually are, in detail.
- [LIMITATIONS.md](../LIMITATIONS.md) — what Efterlev does not do, period.
- AWS official docs:
  - [Amazon Bedrock GovCloud overview](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-bedrock.html) (canonical link; consult for the latest model availability and region notes).
  - [Bedrock VPC endpoints](https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.html).
  - [IMDSv2 enforcement](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-IMDS-existing-instances.html).
- FedRAMP 20x: [fedramp.gov/20x/](https://www.fedramp.gov/20x/) — the broader 20x program context.
