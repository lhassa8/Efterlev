# aws.vpc_logical_segmentation

Detects `aws_vpc` resources and characterizes their subnet topology.
Reports whether the customer's IaC declares a logical network with
proper segmentation (private + public subnets) — the canonical pattern
KSI-CNA-ULN asks for.

## What it proves

- **SC-7 (Boundary Protection)** — the customer declared an explicit
  VPC in Terraform, providing the structural precondition for any
  boundary policy. Customers running on the AWS default VPC have no
  IaC evidence of conscious network design.
- **SC-7(7) (Split Tunneling / Subsystem Separation)** — when the VPC
  has both private and public subnets, the canonical split-tier
  pattern is evidenced. Only fires when both tiers are present.

## What it does NOT prove

- **Route-table correctness.** A subnet flagged "private" by
  `map_public_ip_on_launch=false` could still route to the internet via
  misconfigured route tables, or vice versa. Route-table inspection is
  a separate concern; v0 does not perform it.
- **NAT-gateway / IGW attachment posture.** Whether the public subnets
  actually attach to an IGW, or the private subnets to a NAT gateway,
  is unverified.
- **Per-rule strictness.** Security-group ingress and NACL egress are
  covered by sibling detectors (`aws.security_group_open_ingress`,
  `aws.nacl_open_egress`).
- **Runtime traffic-flow enforcement.** This detector evidences the
  declaration; whether the deployed network actually behaves as
  declared is runtime-cloud-state correlation (v1.5+).
- **Multi-AZ resilience.** Whether subnets span multiple availability
  zones is a separate concern (KSI-CNA-OFA, planned).

## KSI mapping

**KSI-CNA-ULN ("Using Logical Networking").** FRMR 0.9.43-beta lists
SC-7 and SC-7(7) in this KSI's `controls` array.

## Subnet classification

A subnet is **public** when `map_public_ip_on_launch=true` and **private**
otherwise (the AWS and Terraform default). This matches the AWS console
shorthand for what makes a subnet "public." Intra-VPC routing nuances
(NAT gateway presence, IGW attachment) are NOT inspected at v0.

## Segmentation states

| State | Meaning | Controls evidenced |
|---|---|---|
| `declared` | VPC + at least one private AND public subnet | SC-7, SC-7(7) |
| `single_tier` | VPC + subnets, but only one tier | SC-7 |
| `undefined` | VPC declared, no subnets matched its `vpc_id` | SC-7 |

`single_tier` and `undefined` Evidence carries a `gap` field with a
one-line explanation of what's missing or ambiguous.

## Example

Input:

```hcl
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
}

resource "aws_subnet" "private_a" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.2.0/24"
}
```

Output:

```json
{
  "detector_id": "aws.vpc_logical_segmentation",
  "ksis_evidenced": ["KSI-CNA-ULN"],
  "controls_evidenced": ["SC-7", "SC-7(7)"],
  "content": {
    "resource_type": "aws_vpc",
    "resource_name": "main",
    "cidr_block": "10.0.0.0/16",
    "subnet_count": 2,
    "private_subnet_count": 1,
    "public_subnet_count": 1,
    "segmentation_state": "declared"
  }
}
```

## Fixtures

- `fixtures/should_match/declared.tf` — VPC + private + public subnets
  → `segmentation_state="declared"`.
- `fixtures/should_not_match/single_tier_private.tf` — VPC + private
  subnets only → `segmentation_state="single_tier"` with a gap.
- `fixtures/should_not_match/undefined.tf` — VPC declared with no
  subnets → `segmentation_state="undefined"`.
