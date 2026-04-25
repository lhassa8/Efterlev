# `aws.nacl_open_egress`

Flags Network ACL egress rules that allow all protocols to `0.0.0.0/0` or `::/0`.

## What this detector evidences

- **KSI-CNA-RNT** (Restricting Network Traffic) and **KSI-CNA-MAT** (Minimizing Attack Surface).
- **800-53 controls:** SC-7, SC-7(5).

## What it proves

A NACL — defined either as `aws_network_acl` with an inline `egress` block, or as a standalone `aws_network_acl_rule` with `egress = true` — has a rule with:
- `rule_action = "allow"`, AND
- `protocol = "-1"` (all protocols), AND
- `cidr_block = "0.0.0.0/0"` OR `ipv6_cidr_block = "::/0"`.

## What it does NOT prove

- That any subnet uses this NACL. NACLs only matter when associated with a subnet.
- That egress isn't constrained elsewhere (route tables, NAT-gateway absence, organizational SCPs).
- That the AWS-default NACL isn't already wide-open. AWS's default NACL has `0.0.0.0/0` egress allowed, and customers don't typically tighten it. The detector inspects only resources explicitly authored in the Terraform — if no `aws_network_acl` resource is declared, no evidence is emitted, even though the default NACL is permissive.

## Detection signal

A rule matches when ALL of: `rule_action="allow"`, `protocol="-1"`, and either `cidr_block="0.0.0.0/0"` or `ipv6_cidr_block="::/0"`.

A rule with restricted protocol (e.g., 443) or restricted CIDR (e.g., `10.0.0.0/8`) is not flagged.

## Known limitations

- The detector is single-resource-shaped — it does not check whether the NACL is associated with any subnet.
- A common pattern is "open NACL egress + restrictive security-group egress" — defense-in-depth at the SG layer. The detector flags the NACL regardless; the Gap Agent contextualizes whether the SG-layer restriction makes the NACL finding informational rather than a real exposure.
