"""Fixture-driven tests for `aws.nacl_open_egress`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.nacl_open_egress.detector import detect
from efterlev.models import SourceRef, TerraformResource
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "nacl_open_egress"
)


def _run(path: Path) -> list:
    return detect(parse_terraform_file(path))


def test_wide_open_nacl_emits_finding() -> None:
    results = _run(DETECTOR_DIR / "fixtures" / "should_match" / "wide_open_nacl.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.nacl_open_egress"
    assert set(ev.ksis_evidenced) == {"KSI-CNA-RNT", "KSI-CNA-MAT"}
    assert "SC-7" in ev.controls_evidenced
    assert "SC-7(5)" in ev.controls_evidenced
    assert ev.content["origin"] == "inline_egress"
    assert ev.content["exposure_state"] == "all_traffic_to_world"
    assert ev.content["protocol"] == "-1"
    assert ev.content["open_ipv4"] is True


def test_restricted_egress_to_443_emits_no_evidence() -> None:
    """Egress to port 443 only is not all-traffic-to-anywhere."""
    results = _run(DETECTOR_DIR / "fixtures" / "should_not_match" / "restricted_egress.tf")
    assert results == []


def test_standalone_nacl_rule_egress_open_emits_finding() -> None:
    resource = TerraformResource(
        type="aws_network_acl_rule",
        name="public_egress",
        body={
            "network_acl_id": "acl-abc123",
            "rule_number": 100,
            "egress": True,
            "rule_action": "allow",
            "protocol": "-1",
            "cidr_block": "0.0.0.0/0",
        },
        source_ref=SourceRef(file=Path("rule.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["origin"] == "standalone_rule"


def test_standalone_nacl_rule_ingress_is_ignored() -> None:
    """The detector is egress-only."""
    resource = TerraformResource(
        type="aws_network_acl_rule",
        name="public_ingress",
        body={
            "network_acl_id": "acl-abc123",
            "rule_number": 100,
            "egress": False,
            "rule_action": "allow",
            "protocol": "-1",
            "cidr_block": "0.0.0.0/0",
        },
        source_ref=SourceRef(file=Path("rule.tf"), line_start=1, line_end=10),
    )
    assert detect([resource]) == []


def test_deny_rule_is_ignored() -> None:
    """A deny rule with -1 protocol is the *good* shape, not a finding."""
    resource = TerraformResource(
        type="aws_network_acl",
        name="default_deny",
        body={
            "egress": [
                {
                    "rule_no": 100,
                    "rule_action": "deny",
                    "protocol": "-1",
                    "cidr_block": "0.0.0.0/0",
                }
            ]
        },
        source_ref=SourceRef(file=Path("nacl.tf"), line_start=1, line_end=10),
    )
    assert detect([resource]) == []


def test_ipv6_open_egress_emits_finding() -> None:
    resource = TerraformResource(
        type="aws_network_acl",
        name="ipv6_open",
        body={
            "egress": [
                {
                    "rule_no": 100,
                    "rule_action": "allow",
                    "protocol": "-1",
                    "ipv6_cidr_block": "::/0",
                }
            ]
        },
        source_ref=SourceRef(file=Path("nacl.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["open_ipv6"] is True
    assert results[0].content["open_ipv4"] is False
