"""Network-ACL open-egress detector.

Flags NACL rules that allow egress to `0.0.0.0/0` (or `::/0`) on
`protocol = "-1"` (all traffic, all ports). NACLs sit in front of
security groups and provide stateless boundary control; an
all-traffic-anywhere egress rule effectively renders the NACL a no-op
for outbound traffic.

Two AWS resource shapes are inspected:
  - `aws_network_acl` with inline `egress { ... }` blocks.
  - `aws_network_acl_rule` standalone resources with `egress = true`
    (older syntax) or `rule_action = "allow"` and a separate egress flag.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-CNA-RNT (Restricting Network Traffic) — sc-7.5.
  - KSI-CNA-MAT (Minimizing Attack Surface) — broader sc-7 family.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_OPEN_IPV4 = "0.0.0.0/0"
_OPEN_IPV6 = "::/0"


@detector(
    id="aws.nacl_open_egress",
    ksis=["KSI-CNA-RNT", "KSI-CNA-MAT"],
    controls=["SC-7", "SC-7(5)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence for each NACL egress rule that allows all-traffic-to-anywhere.

    Evidences (800-53):  SC-7 (Boundary Protection), SC-7(5) (Deny by Default).
    Evidences (KSI):     KSI-CNA-RNT, KSI-CNA-MAT.
    Does NOT prove:      that any subnet uses this NACL; that egress
                         isn't otherwise constrained by route tables,
                         the absence of a NAT gateway, or organizational
                         SCPs; the AWS-default NACL has 0.0.0.0/0 egress
                         allowed by default — this detector only inspects
                         resources explicitly authored in the Terraform.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type == "aws_network_acl":
            out.extend(_emit_from_inline_egress(r, now))
        elif r.type == "aws_network_acl_rule":
            ev = _emit_from_standalone_rule(r, now)
            if ev is not None:
                out.append(ev)

    return out


def _emit_from_inline_egress(r: TerraformResource, now: datetime) -> list[Evidence]:
    egress = r.body.get("egress")
    if egress is None:
        return []

    blocks: list[dict[str, Any]]
    if isinstance(egress, dict):
        blocks = [egress]
    elif isinstance(egress, list):
        blocks = [b for b in egress if isinstance(b, dict)]
    else:
        return []

    out: list[Evidence] = []
    for block in blocks:
        ev = _classify_block(r, block, now, origin="inline_egress")
        if ev is not None:
            out.append(ev)
    return out


def _emit_from_standalone_rule(r: TerraformResource, now: datetime) -> Evidence | None:
    # `aws_network_acl_rule` represents egress with `egress = true`.
    egress_flag = r.body.get("egress")
    if egress_flag is not True:
        return None
    return _classify_block(r, r.body, now, origin="standalone_rule")


def _classify_block(
    r: TerraformResource,
    block: dict[str, Any],
    now: datetime,
    *,
    origin: str,
) -> Evidence | None:
    """Build Evidence for a single egress block if it warrants one."""
    rule_action = block.get("rule_action") or block.get("action")
    if rule_action != "allow":
        return None

    protocol = _coerce_str(block.get("protocol"))
    cidr_v4 = _coerce_str(block.get("cidr_block"))
    cidr_v6 = _coerce_str(block.get("ipv6_cidr_block"))

    if protocol != "-1":
        return None
    if cidr_v4 != _OPEN_IPV4 and cidr_v6 != _OPEN_IPV6:
        return None

    return Evidence.create(
        detector_id="aws.nacl_open_egress",
        ksis_evidenced=["KSI-CNA-RNT", "KSI-CNA-MAT"],
        controls_evidenced=["SC-7", "SC-7(5)"],
        source_ref=r.source_ref,
        content={
            "resource_type": r.type,
            "resource_name": r.name,
            "origin": origin,
            "exposure_state": "all_traffic_to_world",
            "protocol": protocol,
            "open_ipv4": cidr_v4 == _OPEN_IPV4,
            "open_ipv6": cidr_v6 == _OPEN_IPV6,
            "gap": "NACL egress allows all protocols to 0.0.0.0/0 or ::/0 unconditionally",
        },
        timestamp=now,
    )


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
