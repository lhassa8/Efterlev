"""Fixture-driven tests for `aws.nacl_restrictiveness`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.nacl_restrictiveness.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "nacl_restrictiveness"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def _ref() -> SourceRef:
    return SourceRef(file=Path("nacl.tf"), line_start=1, line_end=10)


# --- fixtures: posture states ----------------------------------------------


def test_restrictive_nacl_emits_evidence_with_sc_7_and_sc_7_5() -> None:
    # Restrictive posture: rules in both directions, explicit deny
    # present, no mgmt ports open. Evidences SC-7 + SC-7(5).
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "restrictive_nacl.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.nacl_restrictiveness"
    assert set(ev.ksis_evidenced) == {"KSI-CNA-RNT", "KSI-CNA-MAT"}
    assert ev.content["posture_state"] == "restrictive"
    assert ev.content["has_explicit_deny"] is True
    assert ev.content["mgmt_ports_open_to_world"] == 0
    assert "SC-7" in ev.controls_evidenced
    assert "SC-7(5)" in ev.controls_evidenced
    # Restrictive posture does NOT carry a gap field.
    assert "gap" not in ev.content


def test_permissive_nacl_emits_evidence_with_gap() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "permissive_nacl.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["posture_state"] == "permissive"
    assert ev.content["ingress_open_to_world"] is True
    assert ev.content["egress_unrestricted"] is True
    assert "gap" in ev.content
    assert "ingress" in ev.content["gap"]
    assert "egress" in ev.content["gap"]


def test_mgmt_port_open_emits_partially_restrictive_with_gap() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "mgmt_port_open.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["posture_state"] == "partially_restrictive"
    assert ev.content["mgmt_ports_open_to_world"] == 1
    assert "gap" in ev.content
    assert "management port" in ev.content["gap"]


def test_empty_nacl_emits_evidence_with_empty_gap() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "empty_nacl.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.content["posture_state"] == "empty"
    assert ev.content["ingress_rule_count"] == 0
    assert ev.content["egress_rule_count"] == 0
    # Empty NACL doesn't get SC-7(5).
    assert "SC-7(5)" not in ev.controls_evidenced
    assert "no associated rules" in ev.content["gap"]


def test_no_nacls_emits_no_evidence() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "no_nacls.tf")
    assert results == []


# --- standalone aws_network_acl_rule resolution ---------------------------


def test_standalone_rule_attaches_to_named_nacl() -> None:
    nacl = TerraformResource(
        type="aws_network_acl",
        name="private",
        body={},
        source_ref=_ref(),
    )
    deny_rule = TerraformResource(
        type="aws_network_acl_rule",
        name="deny_all",
        body={
            "network_acl_id": "${aws_network_acl.private.id}",
            "egress": False,
            "rule_action": "deny",
            "protocol": "-1",
            "cidr_block": "0.0.0.0/0",
            "from_port": 0,
            "to_port": 65535,
        },
        source_ref=_ref(),
    )
    allow_rule = TerraformResource(
        type="aws_network_acl_rule",
        name="allow_443",
        body={
            "network_acl_id": "${aws_network_acl.private.id}",
            "egress": False,
            "rule_action": "allow",
            "protocol": "tcp",
            "cidr_block": "10.0.0.0/8",
            "from_port": 443,
            "to_port": 443,
        },
        source_ref=_ref(),
    )
    egress_rule = TerraformResource(
        type="aws_network_acl_rule",
        name="allow_egress_443",
        body={
            "network_acl_id": "${aws_network_acl.private.id}",
            "egress": True,
            "rule_action": "allow",
            "protocol": "tcp",
            "cidr_block": "0.0.0.0/0",
            "from_port": 443,
            "to_port": 443,
        },
        source_ref=_ref(),
    )
    results = detect([nacl, deny_rule, allow_rule, egress_rule])
    assert len(results) == 1
    ev = results[0]
    assert ev.content["ingress_rule_count"] == 2
    assert ev.content["egress_rule_count"] == 1
    assert ev.content["has_explicit_deny"] is True
    assert ev.content["posture_state"] == "restrictive"


def test_standalone_rule_with_unmatched_nacl_id_is_ignored() -> None:
    # A standalone rule referencing a NACL not in the resource list
    # should not affect any NACL's posture (no orphan attachment).
    nacl = TerraformResource(
        type="aws_network_acl",
        name="other",
        body={},
        source_ref=_ref(),
    )
    orphan_rule = TerraformResource(
        type="aws_network_acl_rule",
        name="orphan",
        body={
            "network_acl_id": "${aws_network_acl.different.id}",
            "egress": False,
            "rule_action": "deny",
            "protocol": "-1",
            "cidr_block": "0.0.0.0/0",
        },
        source_ref=_ref(),
    )
    results = detect([nacl, orphan_rule])
    assert len(results) == 1
    # The "other" NACL stays empty since the rule doesn't reference it.
    assert results[0].content["ingress_rule_count"] == 0
    assert results[0].content["posture_state"] == "empty"


# --- mgmt-port detection edge cases -----------------------------------------


def test_mgmt_port_inside_range_counts() -> None:
    # An ingress rule with from=20 to=25 covers SSH (22).
    nacl = TerraformResource(
        type="aws_network_acl",
        name="range",
        body={
            "ingress": [
                {
                    "rule_no": 100,
                    "rule_action": "allow",
                    "protocol": "tcp",
                    "from_port": 20,
                    "to_port": 25,
                    "cidr_block": "0.0.0.0/0",
                }
            ],
            "egress": [
                {
                    "rule_no": 100,
                    "rule_action": "allow",
                    "protocol": "tcp",
                    "from_port": 443,
                    "to_port": 443,
                    "cidr_block": "10.0.0.0/8",
                }
            ],
        },
        source_ref=_ref(),
    )
    results = detect([nacl])
    assert results[0].content["mgmt_ports_open_to_world"] == 1


def test_mgmt_port_blocked_by_non_world_cidr_does_not_count() -> None:
    # SSH allowed only from internal CIDR — not a finding.
    nacl = TerraformResource(
        type="aws_network_acl",
        name="internal",
        body={
            "ingress": [
                {
                    "rule_no": 100,
                    "rule_action": "allow",
                    "protocol": "tcp",
                    "from_port": 22,
                    "to_port": 22,
                    "cidr_block": "10.0.0.0/8",
                },
                {
                    "rule_no": 200,
                    "rule_action": "deny",
                    "protocol": "-1",
                    "from_port": 0,
                    "to_port": 65535,
                    "cidr_block": "0.0.0.0/0",
                },
            ],
            "egress": [
                {
                    "rule_no": 100,
                    "rule_action": "allow",
                    "protocol": "tcp",
                    "from_port": 443,
                    "to_port": 443,
                    "cidr_block": "0.0.0.0/0",
                }
            ],
        },
        source_ref=_ref(),
    )
    results = detect([nacl])
    assert results[0].content["mgmt_ports_open_to_world"] == 0
    assert results[0].content["posture_state"] == "restrictive"


def test_ipv6_open_with_mgmt_port_counts() -> None:
    # IPv6 ::/0 counts as "open to world" the same as 0.0.0.0/0.
    nacl = TerraformResource(
        type="aws_network_acl",
        name="ipv6_ssh",
        body={
            "ingress": [
                {
                    "rule_no": 100,
                    "rule_action": "allow",
                    "protocol": "tcp",
                    "from_port": 22,
                    "to_port": 22,
                    "ipv6_cidr_block": "::/0",
                }
            ],
            "egress": [
                {
                    "rule_no": 100,
                    "rule_action": "allow",
                    "protocol": "tcp",
                    "from_port": 443,
                    "to_port": 443,
                    "cidr_block": "0.0.0.0/0",
                }
            ],
        },
        source_ref=_ref(),
    )
    results = detect([nacl])
    assert results[0].content["mgmt_ports_open_to_world"] == 1


# --- SC-7(5) attribution depends on explicit deny ---------------------------


def test_no_explicit_deny_omits_sc_7_5_evidence() -> None:
    # NACL with allow rules only (relying on AWS implicit deny) gets SC-7
    # but not SC-7(5).
    nacl = TerraformResource(
        type="aws_network_acl",
        name="implicit_deny_only",
        body={
            "ingress": [
                {
                    "rule_no": 100,
                    "rule_action": "allow",
                    "protocol": "tcp",
                    "from_port": 443,
                    "to_port": 443,
                    "cidr_block": "10.0.0.0/8",
                }
            ],
            "egress": [
                {
                    "rule_no": 100,
                    "rule_action": "allow",
                    "protocol": "tcp",
                    "from_port": 443,
                    "to_port": 443,
                    "cidr_block": "10.0.0.0/8",
                }
            ],
        },
        source_ref=_ref(),
    )
    results = detect([nacl])
    ev = results[0]
    assert ev.content["has_explicit_deny"] is False
    assert "SC-7" in ev.controls_evidenced
    assert "SC-7(5)" not in ev.controls_evidenced
    # Without explicit deny, the NACL is partially_restrictive.
    assert ev.content["posture_state"] == "partially_restrictive"
    assert "explicit deny" in ev.content["gap"]
