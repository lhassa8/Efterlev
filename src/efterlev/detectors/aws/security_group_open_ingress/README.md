# `aws.security_group_open_ingress`

Flags AWS security-group ingress rules that allow traffic from `0.0.0.0/0` or `::/0` on any port other than the standard public-web ports (80 and 443).

## What this detector evidences

- **KSI-CNA-RNT** (Restricting Network Traffic) — open-ingress rules are the canonical failure mode for "deny by default, allow by exception."
- **KSI-CNA-MAT** (Minimizing Attack Surface) — same evidence, different framing.
- **800-53 controls:** SC-7 (Boundary Protection), SC-7(3) (Access Points), SC-7(5) (Deny by Default, Allow by Exception).

## What it proves

A security-group rule (either inline `ingress` block on `aws_security_group` or a standalone `aws_security_group_rule`) defined in the Terraform allows ingress from any IPv4 or IPv6 address on a port outside `{80, 443}`.

## What it does NOT prove

- That the security group is attached to a reachable resource. An open-ingress SG that's not attached to anything is a hygiene issue, not an exposure.
- That the upstream VPC topology (subnets, route tables, NAT gateways, IGWs) actually delivers public traffic to the resource the SG protects. This cross-resource reasoning is Gap Agent territory.
- That the application listening on the port doesn't enforce its own auth (TLS mutual auth, OAuth, IP-allowlist at L7, etc.).
- That the rule is unused at runtime (CloudTrail flow-log analysis would be needed for that, and that's runtime cloud-API scanning — out of scope at v0.1.0).

## Why ports 80 and 443 are excluded

Public web traffic is intentionally open-to-the-world for SaaS. Flagging every 80/443 rule would flood the Gap report with non-findings. We deliberately err on the side of *under*-reporting at known-public ports rather than burying real findings under noise. If a customer needs to gate even public-web ports through a stricter boundary (typical for FedRAMP High), they configure that in the network ACL or WAF layer, which is a different detector.

## Detection signal in detail

A rule matches when:

- `cidr_blocks` contains `0.0.0.0/0`, OR `ipv6_cidr_blocks` contains `::/0`, AND
- the port range (`from_port`–`to_port`) is NOT entirely within `{80, 443}`.

Edge cases the detector handles:

- **Standalone `aws_security_group_rule`** with `type = "ingress"` is inspected the same way as inline `ingress` blocks. Egress rules are ignored (this detector is ingress-only).
- **Prefix-list-based rules** (`prefix_list_ids` set without literal CIDRs) render as opaque from IaC alone; emitted as `exposure_state="unparseable"` so the Gap Agent can surface the uncertainty rather than silently passing.
- **Port range covering both 80/443 and a non-web port** (e.g., 80–8080) is flagged because the range includes ports outside the public-web set.

## Example output

A `should_match` fixture with SSH open to the world produces evidence like:

```json
{
  "resource_type": "aws_security_group",
  "resource_name": "bastion",
  "origin": "inline_ingress",
  "exposure_state": "open_to_world",
  "from_port": 22,
  "to_port": 22,
  "protocol": "tcp",
  "open_ipv4": true,
  "open_ipv6": false,
  "gap": "ingress allows 0.0.0.0/0 on ports 22-22"
}
```

## Known limitations (logged for transparency)

- **Custom essential-port lists.** Some customers will legitimately want, say, port 3389 (RDP) open to a specific corporate-VPN CIDR but not to `0.0.0.0/0`. That's a customer-specific allowlist, out of scope for a generic detector. If the rule has `0.0.0.0/0`, it gets flagged regardless of port.
- **Compounded rules.** If a customer splits an open-ingress configuration across multiple rules (e.g., one rule for IPv4, one for IPv6), the detector flags each rule independently — the user sees two evidence records for what is conceptually one finding. The Gap Agent renders these together when they share a `resource_name`.
