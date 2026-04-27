"""VPC logical-segmentation detector.

Looks for `aws_vpc` resources and characterizes their subnet topology.
KSI-CNA-ULN ("Using Logical Networking") asks the customer to use logical
networking constructs to enforce traffic flow — VPCs, subnets, route
tables. Declaring an explicit VPC with both private and public subnets
is the canonical evidence shape: the customer is segmenting their
network rather than relying on the default-VPC sprawl AWS gives every
account by default.

This detector reports VPC-level posture, not per-rule posture. The
existing detectors `aws.security_group_open_ingress` and
`aws.nacl_open_egress` cover boundary-rule strictness (KSI-CNA-RNT /
KSI-CNA-MAT). This detector is complementary: it asks "does the
customer's IaC declare a logical network at all?", which is the
precondition for any of those rules to be meaningful.

Subnet classification heuristic (per-resource): a subnet with
`map_public_ip_on_launch=true` is public; without it (or explicit
`false`) it's private. This matches the AWS console and Terraform
defaults; intra-VPC routing nuances (NAT gateway, IGW attachment)
require route-table inspection that v0 does not perform — flagged as
"does not prove" in the README.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-CNA-ULN lists `sc-7` and `sc-7.7` in its `controls` array.
    The detector evidences SC-7 (Boundary Protection) at the
    structural-declaration level and SC-7(7) (Split Tunneling /
    Subsystem Separation) when both private and public subnets are
    declared.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.vpc_logical_segmentation",
    ksis=["KSI-CNA-ULN"],
    controls=["SC-7", "SC-7(7)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one Evidence per `aws_vpc`, characterizing its subnet topology.

    Evidences (800-53):  SC-7 (Boundary Protection — declaring an explicit
                         VPC is the structural precondition for any
                         boundary policy), SC-7(7) (Split Tunneling /
                         Subsystem Separation — when both private and
                         public subnets coexist).
    Evidences (KSI):     KSI-CNA-ULN (Using Logical Networking).
    Does NOT prove:      route-table correctness (subnets with public IPs
                         could still route only through a NAT gateway, or
                         vice-versa), NAT/IGW attachment, NACL strictness
                         (separate detector), security-group posture
                         (separate detectors), or runtime traffic-flow
                         enforcement.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    vpcs = [r for r in resources if r.type == "aws_vpc"]
    subnets = [r for r in resources if r.type == "aws_subnet"]

    for vpc in vpcs:
        vpc_subnets = _subnets_for_vpc(subnets, vpc)
        out.append(_emit_vpc_evidence(vpc, vpc_subnets, now))

    return out


def _subnets_for_vpc(
    subnets: list[TerraformResource],
    vpc: TerraformResource,
) -> list[TerraformResource]:
    """Pair subnets with their owning VPC by `vpc_id` Terraform reference.

    `vpc_id = aws_vpc.<name>.id` is the canonical reference shape; we
    match on the substring `aws_vpc.<vpc_name>` since python-hcl2
    materializes the reference as the literal string `${aws_vpc.X.id}`
    or similar. A subnet whose vpc_id can't be resolved (computed-only,
    variable-driven) is conservatively included — the caller can
    reason about ambiguity from the declared subnet count.
    """
    matched: list[TerraformResource] = []
    needle = f"aws_vpc.{vpc.name}"
    for s in subnets:
        ref = _coerce_str(s.body.get("vpc_id"))
        if ref is None:
            # Variable-driven vpc_id; can't tell which VPC, so include in
            # every VPC's tally. Real-world Terraform with multiple VPCs
            # almost never uses this pattern — single-VPC repos do.
            matched.append(s)
        elif needle in ref:
            matched.append(s)
    return matched


def _emit_vpc_evidence(
    vpc: TerraformResource,
    subnets: list[TerraformResource],
    now: datetime,
) -> Evidence:
    """Build a single Evidence record for one VPC + its subnets."""
    cidr = _coerce_str(vpc.body.get("cidr_block"))

    public_subnets = [s for s in subnets if _is_public_subnet(s)]
    private_subnets = [s for s in subnets if not _is_public_subnet(s)]

    has_public = len(public_subnets) > 0
    has_private = len(private_subnets) > 0
    subnet_count = len(subnets)

    # Segmentation states:
    #   declared         — VPC + both private and public subnets present
    #                      (canonical pattern: app in private, ingress in
    #                      public); evidences SC-7(7).
    #   single_tier      — VPC + subnets but only one tier (only-private or
    #                      only-public); evidences SC-7 but not SC-7(7).
    #   undefined        — VPC declared with no associated subnets in this
    #                      codebase. May indicate subnet declarations live
    #                      in a separate module / state — Gap Agent should
    #                      classify with the manifest layer's help.
    if has_private and has_public:
        segmentation_state = "declared"
        controls = ["SC-7", "SC-7(7)"]
    elif subnet_count > 0:
        segmentation_state = "single_tier"
        controls = ["SC-7"]
    else:
        segmentation_state = "undefined"
        controls = ["SC-7"]

    content: dict[str, Any] = {
        "resource_type": vpc.type,
        "resource_name": vpc.name,
        "cidr_block": cidr,
        "subnet_count": subnet_count,
        "private_subnet_count": len(private_subnets),
        "public_subnet_count": len(public_subnets),
        "segmentation_state": segmentation_state,
    }
    if segmentation_state == "single_tier":
        tier = "private-only" if has_private else "public-only"
        content["gap"] = (
            f"VPC declared with {tier} subnets only; canonical SC-7(7) split-tier "
            "(private + public) not evidenced."
        )
    elif segmentation_state == "undefined":
        content["gap"] = (
            "VPC declared but no subnets matched its `vpc_id` in this codebase. "
            "Subnets may live in another module or state."
        )

    return Evidence.create(
        detector_id="aws.vpc_logical_segmentation",
        ksis_evidenced=["KSI-CNA-ULN"],
        controls_evidenced=controls,
        source_ref=vpc.source_ref,
        content=content,
        timestamp=now,
    )


def _is_public_subnet(s: TerraformResource) -> bool:
    """A subnet is public iff `map_public_ip_on_launch=true`. Default is False
    in both AWS and Terraform, so absence == private."""
    val = s.body.get("map_public_ip_on_launch")
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() == "true"
    return False


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
