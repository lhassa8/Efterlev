# `aws.nacl_restrictiveness`

Emits one Evidence per `aws_network_acl` summarizing the NACL's
ingress/egress posture. Companion to `aws.nacl_open_egress`: that
detector reports only when something is wrong, this one reports for
every NACL regardless of posture so positive evidence ("yes, your
NACLs are restrictive") flows to the Gap Agent for KSI-CNA-RNT.

## Why this detector exists

Surfaced by the 2026-04-28 dogfood run: a target with 7 NACLs and 14
NACL rules produced an agent narrative for KSI-CNA-RNT reading "no
detector evaluated NACL restrictiveness," because `nacl_open_egress`
found 0 issues and the agent had no positive signal to reason over.
Absence-of-finding is not the same as positive evidence. This detector
fixes that by emitting per-NACL summaries unconditionally.

## What this detector evidences

- **KSI-CNA-RNT** (Restricting Network Traffic) — partial cross-mapping.
- **KSI-CNA-MAT** (Minimizing Attack Surface) — partial cross-mapping.
- **800-53 controls:** SC-7 (Boundary Protection); SC-7(5) (Deny by
  Default) when an explicit deny rule is present.

## What it proves

For each `aws_network_acl`:

1. The NACL exists and is declared in IaC (declaration-layer evidence
   of SC-7 boundary commitment).
2. How many ingress rules and egress rules it has, broken out by
   inline-on-NACL vs standalone `aws_network_acl_rule` resources.
3. Whether any rule is an explicit deny (evidences SC-7(5) Deny by
   Default; AWS's implicit-deny fall-through is semantically equivalent
   but a 3PAO reads explicit deny as intent rather than oversight).
4. How many ingress rules open management ports (SSH/RDP/DB) to
   `0.0.0.0/0` or `::/0` — concrete attack-surface concerns.
5. Whether any allow rule effectively opens the whole boundary
   (`protocol="-1"` or `from_port=0 to_port=65535` to `0.0.0.0/0`)
   in either direction.

## What it does NOT prove

- **NACL → subnet association.** A restrictive NACL declaration does
  not by itself prove the boundary is enforced where the customer
  cares about it. The detector does not consult
  `aws_network_acl_association` resources. A future sibling detector
  could verify each NACL is associated with at least one subnet.
- **Security-group composition.** NACLs are stateless and coarse;
  security groups are stateful and fine-grained. A NACL that allows
  `0.0.0.0/0:443` may be perfectly safe if the security group in
  front restricts further. Pair this detector's output with
  `aws.security_group_open_ingress` for a complete picture.
- **Runtime traffic.** Static IaC analysis cannot observe whether
  the rules block or pass actual packets. A 3PAO's runtime evidence
  (VPC flow logs, GuardDuty findings) covers that layer.
- **Threat-model fit.** Whether the customer's chosen restriction
  matches their actual threat model is a per-organization risk
  decision; the detector reports posture, not adequacy.

## Posture states

| State | Meaning | Controls evidenced |
|---|---|---|
| `restrictive` | rules in both directions; no mgmt ports open to world; explicit deny present | SC-7, SC-7(5) |
| `partially_restrictive` | rules present but ≥1 concerning pattern (mgmt port open / egress unrestricted / no explicit deny) | SC-7 |
| `permissive` | rules present but both ingress and egress allow all-to-world | SC-7 (declaration only) |
| `empty` | NACL declared with no associated rules; AWS default (allow all) takes over | SC-7 (declaration only) |

The `gap` field on non-`restrictive` evidence names the specific
concerns as a semicolon-separated string the agent and reviewer can
read directly.

## Management ports

Hardcoded list, matched what other IaC scanners (Checkov, Trivy, kics)
flag at the same severity:

| Port | Service |
|---|---|
| 22 | SSH |
| 3389 | RDP |
| 1433 | MSSQL |
| 3306 | MySQL |
| 5432 | PostgreSQL |
| 27017 | MongoDB |
| 6379 | Redis |
| 5984 | CouchDB |
| 9200 | Elasticsearch |
| 11211 | Memcached |

## Example

Input:

```hcl
resource "aws_network_acl" "private_subnet" {
  vpc_id = aws_vpc.main.id

  ingress {
    rule_no     = 100
    rule_action = "allow"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_block  = "10.0.0.0/8"
  }

  ingress {
    rule_no     = 200
    rule_action = "deny"
    protocol    = "-1"
    from_port   = 0
    to_port     = 65535
    cidr_block  = "0.0.0.0/0"
  }

  egress {
    rule_no     = 100
    rule_action = "allow"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_block  = "0.0.0.0/0"
  }
}
```

Output:

```json
{
  "detector_id": "aws.nacl_restrictiveness",
  "ksis_evidenced": ["KSI-CNA-RNT", "KSI-CNA-MAT"],
  "controls_evidenced": ["SC-7", "SC-7(5)"],
  "content": {
    "resource_type": "aws_network_acl",
    "resource_name": "private_subnet",
    "ingress_rule_count": 2,
    "egress_rule_count": 1,
    "has_explicit_deny": true,
    "mgmt_ports_open_to_world": 0,
    "ingress_open_to_world": false,
    "egress_unrestricted": false,
    "posture_state": "restrictive"
  }
}
```

## Fixtures

- `fixtures/should_match/restrictive_nacl.tf` — NACL with explicit deny
  rules and narrowly-scoped allow rules → `restrictive`.
- `fixtures/should_match/permissive_nacl.tf` — NACL allowing
  all-traffic-to-0/0 in both directions → `permissive` with gap.
- `fixtures/should_match/mgmt_port_open.tf` — NACL with SSH allowed
  from 0.0.0.0/0 → `partially_restrictive` with gap.
- `fixtures/should_match/empty_nacl.tf` — NACL declared with no
  rules → `empty` with gap.
- `fixtures/should_not_match/no_nacls.tf` — no `aws_network_acl`
  resources → 0 Evidence emitted.
