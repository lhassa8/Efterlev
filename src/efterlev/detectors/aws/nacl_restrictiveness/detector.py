"""Network-ACL per-NACL posture summary detector.

Companion to `aws.nacl_open_egress`. That detector emits Evidence only
when something is wrong (egress allowing 0.0.0.0/0 with protocol "-1").
This detector emits one Evidence per `aws_network_acl` *unconditionally*,
characterizing the NACL's ingress/egress posture so positive evidence
flows to the Gap Agent for KSI-CNA-RNT — not just absence-of-finding.

Why both: the dogfood run on 2026-04-28 against a target with 7 NACLs and
14 NACL rules surfaced an agent narrative that "no detector evaluated
NACL restrictiveness," because `nacl_open_egress` produced 0 findings
(the NACLs were not pathologically open) and the agent had no positive
signal to reason over. The fix is to emit positive evidence whenever a
NACL exists, whether or not it's misconfigured. Reviewers and the agent
can then see "yes, NACL X exists with N ingress + M egress rules and Y
explicit denies" rather than just silence.

NACL-rule resolution: a rule belongs to a NACL when either (a) it's an
inline `ingress`/`egress` block on the `aws_network_acl` itself, or
(b) it's a standalone `aws_network_acl_rule` whose `network_acl_id`
references the NACL by Terraform-resource ref. The two patterns coexist
in real Terraform; the detector handles both.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-CNA-RNT (Restricting Network Traffic) — `sc-7.5`, `cm-7.1`,
    `ac-17.3`. The detector evidences SC-7 (Boundary Protection) at the
    NACL-declaration level and SC-7(5) (Deny by Default) when an
    explicit deny rule is present. CM-7(1) (Periodic Review) and
    AC-17(3) (Managed Access Control Points) are procedural overlays
    not directly evidenceable from IaC; included in `controls_evidenced`
    only when the NACL's posture is structurally restrictive.
  - KSI-CNA-MAT (Minimizing Attack Surface) — broader SC-7 family;
    cross-mapped via the same per-NACL evidence.

Posture states (per NACL):
  - `restrictive` — has both ingress and egress rules; no rules allowing
    `0.0.0.0/0` to the management-port set; at least one explicit deny
    rule present (evidences SC-7(5)).
  - `partially_restrictive` — has rules but at least one concerning
    pattern: management ports open to 0.0.0.0/0, OR egress entirely
    unrestricted, OR no explicit deny rule (relies on AWS implicit deny).
  - `permissive` — has rules and at least one allow-0/0-on-all-ports
    pattern across both directions.
  - `empty` — NACL declared but has no associated rules in the IaC. AWS
    applies the default rules (ingress: allow all; egress: allow all)
    making this functionally equivalent to no boundary.

Management ports: SSH (22), RDP (3389), MSSQL (1433), MySQL (3306),
PostgreSQL (5432), MongoDB (27017), Redis (6379), CouchDB (5984),
Elasticsearch (9200), Memcached (11211). Hardcoded for v0.1.x; the
list matches what other IaC scanners (Checkov, Trivy, kics) flag.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_OPEN_IPV4 = "0.0.0.0/0"
_OPEN_IPV6 = "::/0"

# Management/sensitive ports we flag when allowed from 0.0.0.0/0. Keep
# in sync with the docstring above and with the README. List based on
# what Checkov / Trivy / kics flag at the same severity.
_MGMT_PORTS = frozenset({22, 3389, 1433, 3306, 5432, 27017, 6379, 5984, 9200, 11211})


@detector(
    id="aws.nacl_restrictiveness",
    ksis=["KSI-CNA-RNT", "KSI-CNA-MAT"],
    controls=["SC-7", "SC-7(5)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one Evidence per `aws_network_acl` summarizing its posture.

    Evidences (800-53):  SC-7 (Boundary Protection) for any NACL with
                         at least one rule; SC-7(5) (Deny by Default)
                         when an explicit deny rule is present.
    Evidences (KSI):     KSI-CNA-RNT, KSI-CNA-MAT.
    Does NOT prove:      that any subnet uses this NACL (NACL-association
                         is a separate resource — `aws_network_acl_association`
                         — not consulted here); that the rules cover the
                         actual customer threat model; that runtime
                         security-group + NACL composition is correct.
                         Stateless evaluation only — protocol semantics
                         and ephemeral-port handling are not modeled.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    nacls = [r for r in resources if r.type == "aws_network_acl"]
    standalone_rules = [r for r in resources if r.type == "aws_network_acl_rule"]

    for nacl in nacls:
        rules = _collect_rules(nacl, standalone_rules)
        out.append(_emit_nacl_evidence(nacl, rules, now))

    return out


def _collect_rules(
    nacl: TerraformResource,
    standalone_rules: list[TerraformResource],
) -> list[dict[str, Any]]:
    """Materialize one normalized rule dict per ingress/egress entry.

    Inline rules from `aws_network_acl.{ingress,egress}` blocks and
    standalone `aws_network_acl_rule` resources both get normalized to
    the same shape: `{"egress": bool, "rule_action": str, "protocol":
    str, "from_port": int|None, "to_port": int|None, "cidr_block":
    str|None, "ipv6_cidr_block": str|None}`.
    """
    rules: list[dict[str, Any]] = []

    for direction in ("ingress", "egress"):
        blocks = nacl.body.get(direction)
        if blocks is None:
            continue
        if isinstance(blocks, dict):
            blocks = [blocks]
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if isinstance(block, dict):
                rules.append(_normalize_rule(block, egress=(direction == "egress")))

    needle = f"aws_network_acl.{nacl.name}"
    for r in standalone_rules:
        nacl_ref = _coerce_str(r.body.get("network_acl_id"))
        if nacl_ref is None or needle not in nacl_ref:
            continue
        egress_flag = r.body.get("egress")
        is_egress = egress_flag is True or (
            isinstance(egress_flag, str) and egress_flag.lower() == "true"
        )
        rules.append(_normalize_rule(r.body, egress=is_egress))

    return rules


def _normalize_rule(block: dict[str, Any], *, egress: bool) -> dict[str, Any]:
    return {
        "egress": egress,
        "rule_action": _coerce_str(block.get("rule_action") or block.get("action")),
        "protocol": _coerce_str(block.get("protocol")),
        "from_port": _coerce_int(block.get("from_port")),
        "to_port": _coerce_int(block.get("to_port")),
        "cidr_block": _coerce_str(block.get("cidr_block")),
        "ipv6_cidr_block": _coerce_str(block.get("ipv6_cidr_block")),
    }


def _emit_nacl_evidence(
    nacl: TerraformResource,
    rules: list[dict[str, Any]],
    now: datetime,
) -> Evidence:
    ingress = [r for r in rules if not r["egress"]]
    egress = [r for r in rules if r["egress"]]

    has_explicit_deny = any(r["rule_action"] == "deny" for r in rules)
    mgmt_ports_open = _count_mgmt_ports_open(ingress)
    egress_unrestricted = _has_unrestricted_open_rule(egress)
    ingress_unrestricted = _has_unrestricted_open_rule(ingress)

    state = _classify_posture(
        rule_count=len(rules),
        has_explicit_deny=has_explicit_deny,
        mgmt_ports_open=mgmt_ports_open,
        ingress_unrestricted=ingress_unrestricted,
        egress_unrestricted=egress_unrestricted,
    )

    controls = ["SC-7"]
    if has_explicit_deny:
        controls.append("SC-7(5)")

    content: dict[str, Any] = {
        "resource_type": nacl.type,
        "resource_name": nacl.name,
        "ingress_rule_count": len(ingress),
        "egress_rule_count": len(egress),
        "has_explicit_deny": has_explicit_deny,
        "mgmt_ports_open_to_world": mgmt_ports_open,
        "ingress_open_to_world": ingress_unrestricted,
        "egress_unrestricted": egress_unrestricted,
        "posture_state": state,
    }
    gap = _gap_text_for(state, mgmt_ports_open, egress_unrestricted, ingress_unrestricted)
    if gap is not None:
        content["gap"] = gap

    return Evidence.create(
        detector_id="aws.nacl_restrictiveness",
        ksis_evidenced=["KSI-CNA-RNT", "KSI-CNA-MAT"],
        controls_evidenced=controls,
        source_ref=nacl.source_ref,
        content=content,
        timestamp=now,
    )


def _classify_posture(
    *,
    rule_count: int,
    has_explicit_deny: bool,
    mgmt_ports_open: int,
    ingress_unrestricted: bool,
    egress_unrestricted: bool,
) -> str:
    if rule_count == 0:
        return "empty"
    if ingress_unrestricted and egress_unrestricted:
        return "permissive"
    if mgmt_ports_open > 0 or egress_unrestricted or not has_explicit_deny:
        return "partially_restrictive"
    return "restrictive"


def _count_mgmt_ports_open(ingress_rules: list[dict[str, Any]]) -> int:
    """Count ingress allow-rules whose port range overlaps a management port
    AND whose CIDR is open to the world."""
    count = 0
    for r in ingress_rules:
        if r["rule_action"] != "allow":
            continue
        if not _opens_to_world(r):
            continue
        if _range_includes_mgmt_port(r["protocol"], r["from_port"], r["to_port"]):
            count += 1
    return count


def _has_unrestricted_open_rule(rules: list[dict[str, Any]]) -> bool:
    """True iff any allow rule covers all protocols + all ports open to world.

    The "deny everyone, allow narrow" pattern keeps `unrestricted` False;
    the AWS-default-NACL pattern (allow all-protocols-to-0/0) sets it True.
    """
    for r in rules:
        if r["rule_action"] != "allow":
            continue
        if not _opens_to_world(r):
            continue
        if r["protocol"] == "-1":
            return True
        # Protocol-specific but full port range counts too: tcp 0-65535 is
        # functionally equivalent to all-protocols for TCP services.
        if r["from_port"] == 0 and r["to_port"] == 65535:
            return True
    return False


def _opens_to_world(rule: dict[str, Any]) -> bool:
    cidr = rule["cidr_block"]
    ipv6 = rule["ipv6_cidr_block"]
    return bool(cidr == _OPEN_IPV4 or ipv6 == _OPEN_IPV6)


def _range_includes_mgmt_port(
    protocol: str | None, from_port: int | None, to_port: int | None
) -> bool:
    """True iff the rule's protocol + port range includes a management port.

    Protocol "-1" (all protocols) is unconditionally TCP-inclusive, so we
    treat it as covering management ports if the port range overlaps. A
    rule with no port range (None, None) is interpreted as "all ports"
    when protocol is "-1" or "tcp" — the AWS console default for NACL
    rules without explicit ports.
    """
    if protocol not in (None, "-1", "tcp", "6"):
        return False
    if from_port is None and to_port is None:
        # "All ports" — covers every management port.
        return True
    if from_port is None or to_port is None:
        # Half-specified is unusual but defensively handled: treat as
        # singleton port equal to whichever side is set.
        port = from_port if from_port is not None else to_port
        return port in _MGMT_PORTS
    return any(from_port <= p <= to_port for p in _MGMT_PORTS)


def _gap_text_for(
    state: str,
    mgmt_ports_open: int,
    egress_unrestricted: bool,
    ingress_unrestricted: bool,
) -> str | None:
    if state == "restrictive":
        return None
    if state == "empty":
        return (
            "NACL declared with no associated rules; AWS applies the default "
            "(allow all in/out), making this NACL functionally a no-op."
        )
    parts: list[str] = []
    if ingress_unrestricted:
        parts.append("ingress allows all-protocols-to-0/0")
    if egress_unrestricted:
        parts.append("egress allows all-protocols-to-0/0")
    if mgmt_ports_open > 0:
        parts.append(
            f"{mgmt_ports_open} ingress rule(s) open management port(s) (SSH, RDP, "
            "DB ports) to 0.0.0.0/0"
        )
    if not parts:
        # partially_restrictive without an obvious gap means the NACL
        # has no explicit deny rule. Rely on AWS implicit deny only.
        parts.append("no explicit deny rule; relies entirely on AWS implicit deny")
    return "; ".join(parts)


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)


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
