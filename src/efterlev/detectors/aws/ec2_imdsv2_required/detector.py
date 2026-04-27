"""EC2 IMDSv2-required detector.

Inspects every `aws_instance` and `aws_launch_template` resource and
reports whether `metadata_options.http_tokens` is set to `"required"`
(IMDSv2-only) versus `"optional"` (IMDSv1 allowed) or unset
(IMDSv1 allowed by default).

IMDSv2 enforcement is the AWS-documented EC2 baseline-configuration
knob: requiring session tokens defeats the SSRF-against-metadata-service
attack pattern that was the basis of the Capital One breach. Every
serious AWS hardening guide (CIS, AWS FSBP, AWS Well-Architected)
flags `http_tokens != "required"` as a finding. KSI-CNA-IBP
("Implementing Best Practices") asks customers to "implement based on
the host provider's best practices and documented guidance" — IMDSv2
required is exactly that, expressed in IaC.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-CNA-IBP lists `cm-2` (Baseline Configuration), `ac-17.3`
    (Managed Access Control Points), and `pl-10` (Baseline Tailoring).
    The `http_tokens = "required"` knob evidences CM-2 directly
    (it IS the baseline-configuration choice). AC-17(3) and PL-10
    don't fit this resource, so we don't claim them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

# Resource types that have an EC2-style `metadata_options` block.
_INSTANCE_TYPES = {"aws_instance", "aws_launch_template"}


@detector(
    id="aws.ec2_imdsv2_required",
    ksis=["KSI-CNA-IBP"],
    controls=["CM-2"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one Evidence per EC2 instance / launch template.

    Evidences (800-53):  CM-2 (Baseline Configuration). IMDSv2-required
                         IS the AWS-documented EC2 baseline.
    Evidences (KSI):     KSI-CNA-IBP (Implementing Best Practices).
    Does NOT prove:      that all EC2 instances in the boundary are
                         covered by these Terraform resources (a stray
                         console-launched instance won't be flagged);
                         that runtime drift hasn't reverted the setting
                         (Config rules cover that gap).
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type not in _INSTANCE_TYPES:
            continue
        out.append(_emit_imdsv2_evidence(r, now))

    return out


def _emit_imdsv2_evidence(r: TerraformResource, now: datetime) -> Evidence:
    """Build one Evidence record characterizing the instance's IMDS posture."""
    metadata = _extract_metadata_options(r.body)
    http_tokens = _as_str(metadata.get("http_tokens")) if metadata else None
    hop_limit = metadata.get("http_put_response_hop_limit") if metadata else None

    if http_tokens == "required":
        imds_state = "imdsv2_required"
    elif http_tokens == "optional":
        imds_state = "imdsv1_allowed"
    elif metadata is None:
        # No `metadata_options` block at all → AWS default = IMDSv1 + IMDSv2
        # both allowed (i.e. IMDSv1 reachable). Gap.
        imds_state = "metadata_options_unset"
    else:
        imds_state = "unknown"

    content: dict[str, Any] = {
        "resource_type": r.type,
        "resource_name": r.name,
        "imds_state": imds_state,
        "http_tokens": http_tokens,
        "http_put_response_hop_limit": hop_limit,
    }

    if imds_state == "imdsv1_allowed":
        content["gap"] = (
            f"`{r.type}.{r.name}` has `metadata_options.http_tokens = "
            f'"optional"` — IMDSv1 is reachable. Set http_tokens = '
            '"required" to enforce IMDSv2-only and defeat the '
            "metadata-service SSRF pattern."
        )
    elif imds_state == "metadata_options_unset":
        content["gap"] = (
            f"`{r.type}.{r.name}` has no `metadata_options` block. AWS's "
            "default allows both IMDSv1 and IMDSv2; explicitly set "
            'metadata_options { http_tokens = "required" } to enforce '
            "IMDSv2-only."
        )

    return Evidence.create(
        detector_id="aws.ec2_imdsv2_required",
        ksis_evidenced=["KSI-CNA-IBP"],
        controls_evidenced=["CM-2"],
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )


def _extract_metadata_options(body: dict[str, Any]) -> dict[str, Any] | None:
    """Pull `metadata_options` out of either an aws_instance body or an
    aws_launch_template body. python-hcl2 wraps blocks in single-element
    lists; normalize."""
    metadata = body.get("metadata_options")
    if isinstance(metadata, list) and metadata and isinstance(metadata[0], dict):
        metadata = metadata[0]
    if isinstance(metadata, dict):
        return metadata
    return None


def _as_str(value: Any) -> str | None:
    """python-hcl2 occasionally returns strings wrapped in single-element lists."""
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value if isinstance(value, str) else None
