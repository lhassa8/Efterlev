"""Fixture-driven tests for `aws.security_group_open_ingress`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.security_group_open_ingress.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "security_group_open_ingress"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ----------------------------------------------------------


def test_ssh_open_to_world_emits_finding() -> None:
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "ssh_open_to_world.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.security_group_open_ingress"
    assert set(ev.ksis_evidenced) == {"KSI-CNA-RNT", "KSI-CNA-MAT"}
    assert "SC-7" in ev.controls_evidenced
    assert "SC-7(5)" in ev.controls_evidenced
    assert ev.content["resource_type"] == "aws_security_group"
    assert ev.content["resource_name"] == "bastion"
    assert ev.content["origin"] == "inline_ingress"
    assert ev.content["exposure_state"] == "open_to_world"
    assert ev.content["from_port"] == 22
    assert ev.content["to_port"] == 22
    assert ev.content["open_ipv4"] is True
    assert ev.content["open_ipv6"] is False
    assert "0.0.0.0/0" in ev.content["gap"]
    assert "22" in ev.content["gap"]


# --- should_not_match ------------------------------------------------------


def test_ssh_restricted_to_corporate_cidr_emits_nothing() -> None:
    """An ingress rule with a private CIDR is not open-to-world."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "ssh_restricted.tf")
    assert results == []


def test_https_to_world_is_not_a_finding() -> None:
    """Public HTTPS (and HTTP) is the canonical intentional open-to-world.
    Two ingress blocks; neither is a finding."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "https_to_world.tf")
    assert results == []


# --- direct-input shape tests (no Terraform file parsing) ------------------


def test_standalone_ingress_rule_with_open_cidr_emits_finding() -> None:
    """`aws_security_group_rule` with type=ingress and 0.0.0.0/0 cidr."""
    from efterlev.models import SourceRef, TerraformResource

    resource = TerraformResource(
        type="aws_security_group_rule",
        name="open_db",
        body={
            "type": "ingress",
            "from_port": 5432,
            "to_port": 5432,
            "protocol": "tcp",
            "cidr_blocks": ["0.0.0.0/0"],
            "security_group_id": "sg-abc123",
        },
        source_ref=SourceRef(file=Path("rule.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["origin"] == "standalone_rule"
    assert results[0].content["from_port"] == 5432


def test_standalone_egress_rule_is_ignored() -> None:
    """The detector is ingress-only; egress rules don't emit evidence."""
    from efterlev.models import SourceRef, TerraformResource

    resource = TerraformResource(
        type="aws_security_group_rule",
        name="any_egress",
        body={
            "type": "egress",
            "from_port": 0,
            "to_port": 0,
            "protocol": "-1",
            "cidr_blocks": ["0.0.0.0/0"],
            "security_group_id": "sg-abc123",
        },
        source_ref=SourceRef(file=Path("rule.tf"), line_start=1, line_end=10),
    )
    assert detect([resource]) == []


def test_ipv6_open_ingress_on_ssh_emits_finding() -> None:
    """`::/0` on a non-public-web port is the IPv6 equivalent finding."""
    from efterlev.models import SourceRef, TerraformResource

    resource = TerraformResource(
        type="aws_security_group",
        name="bastion_v6",
        body={
            "ingress": [
                {
                    "from_port": 22,
                    "to_port": 22,
                    "protocol": "tcp",
                    "ipv6_cidr_blocks": ["::/0"],
                }
            ]
        },
        source_ref=SourceRef(file=Path("sg.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["open_ipv6"] is True
    assert results[0].content["open_ipv4"] is False


def test_prefix_list_only_rule_emits_unparseable() -> None:
    """A rule using prefix_list_ids without literal CIDRs is opaque from IaC."""
    from efterlev.models import SourceRef, TerraformResource

    resource = TerraformResource(
        type="aws_security_group",
        name="via_prefix_list",
        body={
            "ingress": [
                {
                    "from_port": 22,
                    "to_port": 22,
                    "protocol": "tcp",
                    "prefix_list_ids": ["pl-12345"],
                }
            ]
        },
        source_ref=SourceRef(file=Path("sg.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1
    assert results[0].content["exposure_state"] == "unparseable"
    assert "prefix_list_ids" in results[0].content["reason"]


def test_port_range_spanning_web_and_non_web_emits_finding() -> None:
    """A port range that includes ports outside {80, 443} should match
    even if it includes 80/443 too. 80-8080 spans non-web ports."""
    from efterlev.models import SourceRef, TerraformResource

    resource = TerraformResource(
        type="aws_security_group",
        name="wide_range",
        body={
            "ingress": [
                {
                    "from_port": 80,
                    "to_port": 8080,
                    "protocol": "tcp",
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ]
        },
        source_ref=SourceRef(file=Path("sg.tf"), line_start=1, line_end=10),
    )
    results = detect([resource])
    assert len(results) == 1


def test_inline_ingress_with_no_cidr_blocks_emits_nothing() -> None:
    """An ingress block referencing only a security_group_id (no CIDR)
    is intra-VPC traffic, not open-to-world."""
    from efterlev.models import SourceRef, TerraformResource

    resource = TerraformResource(
        type="aws_security_group",
        name="intra_vpc",
        body={
            "ingress": [
                {
                    "from_port": 5432,
                    "to_port": 5432,
                    "protocol": "tcp",
                    "security_groups": ["sg-app123"],
                }
            ]
        },
        source_ref=SourceRef(file=Path("sg.tf"), line_start=1, line_end=10),
    )
    assert detect([resource]) == []
