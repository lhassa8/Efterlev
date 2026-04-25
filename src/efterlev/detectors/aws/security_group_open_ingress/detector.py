"""Security-group open-ingress detector.

Scans `aws_security_group` (inline `ingress` blocks) and standalone
`aws_security_group_rule` resources for rules that allow ingress from
0.0.0.0/0 or ::/0 on a port other than the standard public-web ports
(80, 443). HTTPS-to-the-world is normal and intentional; SSH-to-the-
world or database-port-to-the-world is the misconfiguration shape this
detector exists to catch.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-CNA-RNT (Restricting Network Traffic) lists `sc-7.5` in its
    controls array. An open-ingress rule from any CIDR is the canonical
    SC-7(5) failure ("deny network traffic by default and allow by
    exception"). Clean mapping — we claim it.
  - KSI-CNA-MAT (Minimizing Attack Surface) also references sc-7.5 plus
    the broader sc-7.3 / sc-7.4 / sc-7.8 family. Listed as a secondary
    mapping in mapping.yaml; the detector evidences both.

The detector explicitly does NOT inspect upstream VPC topology, route
tables, NAT-gateway presence, or whether the SG is actually attached to
a reachable resource. An open-ingress SG that's not attached to anything
is harmless; one attached to a public-subnet EC2 is a real exposure.
That cross-resource analysis is Gap Agent territory, not detector
territory.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

# CIDR blocks that mean "any IPv4" / "any IPv6". Either as a list element
# directly is the open-to-the-world signal we hunt.
_OPEN_IPV4 = "0.0.0.0/0"
_OPEN_IPV6 = "::/0"

# Ports that are routinely public-internet-facing and where 0.0.0.0/0
# ingress is intentional, not a finding. Anything else is suspicious.
# Per the SPEC-14.1 design, this is deliberately small and conservative.
_PUBLIC_WEB_PORTS = frozenset({80, 443})


@detector(
    id="aws.security_group_open_ingress",
    ksis=["KSI-CNA-RNT", "KSI-CNA-MAT"],
    controls=["SC-7", "SC-7(3)", "SC-7(5)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence for each ingress rule open to the world on a non-essential port.

    Evidences (800-53):  SC-7 (Boundary Protection), SC-7(3) (Access Points),
                         SC-7(5) (Deny by Default / Allow by Exception).
    Evidences (KSI):     KSI-CNA-RNT (Restricting Network Traffic),
                         KSI-CNA-MAT (Minimizing Attack Surface).
    Does NOT prove:      that the SG is attached to anything reachable;
                         that the upstream VPC topology actually exposes
                         the port to the internet; that the application
                         listening on the port doesn't enforce its own
                         auth; or that the rule is unused at runtime.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type == "aws_security_group":
            out.extend(_emit_from_inline_ingress(r, now))
        elif r.type == "aws_security_group_rule":
            ev = _emit_from_standalone_rule(r, now)
            if ev is not None:
                out.append(ev)

    return out


def _emit_from_inline_ingress(r: TerraformResource, now: datetime) -> list[Evidence]:
    """Iterate inline `ingress` blocks on an aws_security_group."""
    ingress = r.body.get("ingress")
    if ingress is None:
        return []
    # python-hcl2 represents repeated blocks as a list of dicts. Single-
    # block case may render as a single dict; normalize.
    blocks: list[dict[str, Any]]
    if isinstance(ingress, dict):
        blocks = [ingress]
    elif isinstance(ingress, list):
        blocks = [b for b in ingress if isinstance(b, dict)]
    else:
        return []

    out: list[Evidence] = []
    for block in blocks:
        ev = _classify_block(
            r,
            block,
            now,
            origin="inline_ingress",
        )
        if ev is not None:
            out.append(ev)
    return out


def _emit_from_standalone_rule(r: TerraformResource, now: datetime) -> Evidence | None:
    """Inspect an aws_security_group_rule resource."""
    if r.body.get("type") != "ingress":
        return None
    return _classify_block(r, r.body, now, origin="standalone_rule")


def _classify_block(
    r: TerraformResource,
    block: dict[str, Any],
    now: datetime,
    *,
    origin: str,
) -> Evidence | None:
    """Build an Evidence record for one ingress block, if it warrants one.

    Returns None when the block is restricted (no 0.0.0.0/0 or ::/0) or
    when the open ingress is on a known-public-web port. Otherwise emits
    a finding-shaped Evidence with `gap` populated.
    """
    cidr_v4 = _normalize_cidrs(block.get("cidr_blocks"))
    cidr_v6 = _normalize_cidrs(block.get("ipv6_cidr_blocks"))
    has_prefix_list = block.get("prefix_list_ids") not in (None, [], "")

    open_v4 = _OPEN_IPV4 in cidr_v4
    open_v6 = _OPEN_IPV6 in cidr_v6

    # Prefix-list-based rules are opaque from IaC; flag as unparseable
    # rather than silently passing.
    if has_prefix_list and not (open_v4 or open_v6):
        return Evidence.create(
            detector_id="aws.security_group_open_ingress",
            ksis_evidenced=["KSI-CNA-RNT", "KSI-CNA-MAT"],
            controls_evidenced=["SC-7", "SC-7(3)", "SC-7(5)"],
            source_ref=r.source_ref,
            content={
                "resource_type": r.type,
                "resource_name": r.name,
                "origin": origin,
                "exposure_state": "unparseable",
                "reason": "prefix_list_ids opaque from IaC",
            },
            timestamp=now,
        )

    if not (open_v4 or open_v6):
        return None

    from_port, to_port = _port_range(block)
    on_public_web_port_only = _all_in_public_web(from_port, to_port)
    if on_public_web_port_only:
        return None

    # We have a finding.
    return Evidence.create(
        detector_id="aws.security_group_open_ingress",
        ksis_evidenced=["KSI-CNA-RNT", "KSI-CNA-MAT"],
        controls_evidenced=["SC-7", "SC-7(3)", "SC-7(5)"],
        source_ref=r.source_ref,
        content={
            "resource_type": r.type,
            "resource_name": r.name,
            "origin": origin,
            "exposure_state": "open_to_world",
            "from_port": from_port,
            "to_port": to_port,
            "protocol": _coerce_str(block.get("protocol")),
            "open_ipv4": open_v4,
            "open_ipv6": open_v6,
            "gap": (
                f"ingress allows {_OPEN_IPV4 if open_v4 else _OPEN_IPV6} "
                f"on ports {from_port}-{to_port}"
            ),
        },
        timestamp=now,
    )


def _normalize_cidrs(value: Any) -> list[str]:
    """python-hcl2 yields cidr_blocks as `[["1.2.3.4/32"]]` or `["..."]`."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        flat: list[str] = []
        for item in value:
            if isinstance(item, list):
                flat.extend(str(x) for x in item)
            elif isinstance(item, str):
                flat.append(item)
        return flat
    return []


def _port_range(block: dict[str, Any]) -> tuple[int | None, int | None]:
    """Pull (from_port, to_port). Either may be None when unset/unparseable."""
    return _coerce_int(block.get("from_port")), _coerce_int(block.get("to_port"))


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)


def _all_in_public_web(from_port: int | None, to_port: int | None) -> bool:
    """True iff the port range lies entirely within {80, 443}."""
    if from_port is None or to_port is None:
        return False
    if from_port > to_port:
        return False
    return all(p in _PUBLIC_WEB_PORTS for p in range(from_port, to_port + 1))
