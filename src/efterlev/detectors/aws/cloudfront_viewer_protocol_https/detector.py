"""CloudFront viewer-protocol HTTPS detector.

Inspects every `aws_cloudfront_distribution` resource and reports
whether its `default_cache_behavior` (and any `ordered_cache_behavior`)
forces HTTPS-only viewer connections, plus whether the
`viewer_certificate.minimum_protocol_version` meets a FedRAMP-acceptable
TLS bar (TLSv1.2 or TLSv1.3).

KSI-SVC-VCM ("Validating Communications") asks the customer to validate
the authenticity of communications to/from the boundary; HTTPS at the
edge is the canonical IaC-evidenceable signal. SC-23 (Session
Authenticity) is the 800-53 control behind it; SI-7(1) (Integrity
Checks) is also evidenced because TLS provides per-message integrity.

Sibling to `aws.tls_on_lb_listeners` (KSI-SVC-SNT / SC-8 — confidentiality
on LB listeners) but distinct: SVC-VCM is about session authenticity at
the edge surface (CloudFront), not just transport encryption on the
back-end LB.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-SVC-VCM lists `sc-23` (Session Authenticity) and `si-7.1`
    (Integrity Checks). HTTPS-only viewer policy + TLSv1.2+ minimum is
    direct evidence for both.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

# Viewer-protocol policies that block plaintext HTTP. CloudFront
# accepts: "allow-all", "https-only", "redirect-to-https".
_HTTPS_ONLY_POLICIES = {"https-only", "redirect-to-https"}

# Minimum TLS protocol versions that meet a FedRAMP-acceptable bar.
# CloudFront's options range from SSLv3 (deprecated) up through
# TLSv1.2_2021 and TLSv1.3 (post-2026). Below TLSv1.2 is an automatic
# gap.
_ACCEPTABLE_MIN_TLS = {
    "TLSv1.2_2018",
    "TLSv1.2_2019",
    "TLSv1.2_2021",
    "TLSv1.3",
    # CloudFront's current default is TLSv1; explicitly-set TLSv1.2 only
    # if the customer asked for it.
}


@detector(
    id="aws.cloudfront_viewer_protocol_https",
    ksis=["KSI-SVC-VCM"],
    controls=["SC-23", "SI-7(1)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one Evidence per CloudFront distribution.

    Evidences (800-53):  SC-23 (Session Authenticity) when the viewer
                         policy forces HTTPS; SI-7(1) (Integrity Checks)
                         since TLS provides per-message integrity.
    Evidences (KSI):     KSI-SVC-VCM (Validating Communications).
    Does NOT prove:      that the certificate is valid for the served
                         hostname; that origin-protocol-policy is also
                         HTTPS (different surface — origin connections);
                         that HSTS or secure-cookie headers are set —
                         those live in response-headers policies and
                         the origin application.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_cloudfront_distribution":
            continue
        out.append(_emit_distribution_evidence(r, now))

    return out


def _emit_distribution_evidence(r: TerraformResource, now: datetime) -> Evidence:
    """Build one Evidence record characterizing the distribution's HTTPS posture."""
    behaviors = _collect_cache_behaviors(r.body)
    behavior_states = [_classify_behavior(b) for b in behaviors]

    if not behavior_states:
        # No default_cache_behavior parseable — unusual; report as unknown.
        viewer_state = "unknown"
        gap_behaviors: list[str] = []
    elif all(s == "https_only" for s in behavior_states):
        viewer_state = "https_only"
        gap_behaviors = []
    elif any(s == "allow_all" for s in behavior_states):
        viewer_state = "allows_http"
        gap_behaviors = [
            f"behavior #{i}: {s}" for i, s in enumerate(behavior_states) if s == "allow_all"
        ]
    else:
        viewer_state = "mixed"
        gap_behaviors = [
            f"behavior #{i}: {s}" for i, s in enumerate(behavior_states) if s != "https_only"
        ]

    minimum_tls = _extract_minimum_tls(r.body)
    tls_meets_bar = minimum_tls in _ACCEPTABLE_MIN_TLS if minimum_tls else False

    content: dict[str, Any] = {
        "resource_type": r.type,
        "resource_name": r.name,
        "viewer_state": viewer_state,
        "behavior_count": len(behaviors),
        "minimum_protocol_version": minimum_tls,
        "tls_meets_fedramp_bar": tls_meets_bar,
    }

    gap_parts: list[str] = []
    if viewer_state in {"allows_http", "mixed"}:
        gap_parts.append(
            f"viewer_protocol_policy permits plaintext HTTP ({', '.join(gap_behaviors)})"
        )
    if minimum_tls and not tls_meets_bar:
        gap_parts.append(
            f"minimum_protocol_version={minimum_tls!r} is below FedRAMP-acceptable TLSv1.2_2018+"
        )
    elif minimum_tls is None:
        gap_parts.append(
            "viewer_certificate.minimum_protocol_version is not set; "
            "CloudFront defaults to TLSv1, below the FedRAMP bar"
        )
    if gap_parts:
        content["gap"] = "; ".join(gap_parts)

    return Evidence.create(
        detector_id="aws.cloudfront_viewer_protocol_https",
        ksis_evidenced=["KSI-SVC-VCM"],
        controls_evidenced=["SC-23", "SI-7(1)"],
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )


def _collect_cache_behaviors(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of cache-behavior blocks (default + ordered).

    python-hcl2 renders each `*_cache_behavior` block as either a dict
    or a single-element list of dicts; normalize.
    """
    out: list[dict[str, Any]] = []

    default = body.get("default_cache_behavior")
    if isinstance(default, dict):
        out.append(default)
    elif isinstance(default, list):
        out.extend(b for b in default if isinstance(b, dict))

    ordered = body.get("ordered_cache_behavior")
    if isinstance(ordered, dict):
        out.append(ordered)
    elif isinstance(ordered, list):
        out.extend(b for b in ordered if isinstance(b, dict))

    return out


def _classify_behavior(behavior: dict[str, Any]) -> str:
    """Return one of: 'https_only', 'allow_all', 'unknown'."""
    policy = _as_str(behavior.get("viewer_protocol_policy"))
    if policy is None:
        return "unknown"
    if policy in _HTTPS_ONLY_POLICIES:
        return "https_only"
    if policy == "allow-all":
        return "allow_all"
    return "unknown"


def _extract_minimum_tls(body: dict[str, Any]) -> str | None:
    """Pull `viewer_certificate.minimum_protocol_version` out of the body."""
    cert = body.get("viewer_certificate")
    if isinstance(cert, list) and cert and isinstance(cert[0], dict):
        cert = cert[0]
    if not isinstance(cert, dict):
        return None
    return _as_str(cert.get("minimum_protocol_version"))


def _as_str(value: Any) -> str | None:
    """python-hcl2 occasionally returns strings wrapped in single-element lists."""
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value if isinstance(value, str) else None
