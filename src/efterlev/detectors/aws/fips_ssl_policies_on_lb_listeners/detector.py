"""AWS LB listener FIPS ssl_policy detector.

Complement to `aws.tls_on_lb_listeners`: that detector proves the
listener accepts TLS at all; this one proves the `ssl_policy` chosen
for it is a FIPS-approved / forward-secrecy policy (SC-13 territory,
not SC-8). The two together answer the full "transport is encrypted
with FIPS-grade crypto" question FedRAMP 20x evaluates.

KSI coverage per CLAUDE.md §"Detection scope":
  - KSI-SVC-VRI (Validating Resource Integrity) — primary; SC-13 is
    the 800-53 control this KSI references.
  - KSI-SVC-SNT (Securing Network Traffic) — reinforces; the FIPS
    policy is the algorithmic layer of the network-traffic-security
    story (whereas aws.tls_on_lb_listeners covers the presence layer).

FIPS-approved policy recognition is conservative: we allow policies
starting with `ELBSecurityPolicy-FS-` (forward-secrecy families) and
`ELBSecurityPolicy-TLS13-` (TLS 1.3 families, which AWS publishes as
FIPS 140-3 compatible). Everything else — including the common legacy
`ELBSecurityPolicy-2016-08` — is flagged as `not_fips_approved`. A
user with a genuinely FIPS-aligned custom policy outside the allowlist
will see false negatives here; that's acceptable for v0 and easy to
extend.

Only emits evidence for TLS/HTTPS listeners. HTTP listeners are
covered by `aws.tls_on_lb_listeners` and have no ssl_policy to
evaluate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_LISTENER_TYPES = {"aws_lb_listener", "aws_alb_listener"}
_TLS_PROTOCOLS = {"HTTPS", "TLS"}

# Conservative FIPS/FedRAMP-aligned ssl_policy prefixes. AWS publishes the
# definitive list in ELB documentation; these two families cover the
# recommendations as of this writing without over-claiming coverage of
# the broader (and less strict) set.
_FIPS_ALIGNED_PREFIXES = (
    "ELBSecurityPolicy-FS-",
    "ELBSecurityPolicy-TLS13-",
)


@detector(
    id="aws.fips_ssl_policies_on_lb_listeners",
    ksis=["KSI-SVC-VRI", "KSI-SVC-SNT"],
    controls=["SC-13"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit FIPS-ssl_policy Evidence for every TLS-enabled LB listener.

    Evidences (KSI):     KSI-SVC-VRI (Validating Resource Integrity) — partial.
                         KSI-SVC-SNT (Securing Network Traffic) — reinforces.
    Evidences (800-53):  SC-13 (Cryptographic Protection).
    Does NOT prove:      (1) certificate strength or key length;
                         (2) runtime cipher-suite negotiation outcomes;
                         (3) cryptographic module validation beyond the
                         AWS-managed policy name — the AWS LB service
                         itself is what terminates TLS, and its
                         cryptographic-module certification is AWS's
                         representation to accept.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type not in _LISTENER_TYPES:
            continue
        protocol = _as_str(r.body.get("protocol"))
        if not protocol or protocol.upper() not in _TLS_PROTOCOLS:
            # Non-TLS listeners are outside this detector's scope.
            continue
        out.append(_emit_evidence(r, protocol, now))

    return out


def _emit_evidence(r: TerraformResource, protocol: str, now: datetime) -> Evidence:
    ssl_policy = _as_str(r.body.get("ssl_policy"))

    if ssl_policy is None:
        fips_state = "unknown"
        gap = (
            "listener is TLS-enabled but declares no ssl_policy; "
            "AWS will apply a default that may not be FIPS-aligned"
        )
    elif any(ssl_policy.startswith(prefix) for prefix in _FIPS_ALIGNED_PREFIXES):
        fips_state = "present"
        gap = None
    else:
        fips_state = "absent"
        gap = (
            f"ssl_policy {ssl_policy!r} is not in the FIPS-aligned "
            "ELBSecurityPolicy-FS-* / ELBSecurityPolicy-TLS13-* families"
        )

    content: dict[str, Any] = {
        "resource_type": r.type,
        "resource_name": r.name,
        "protocol": protocol,
        "ssl_policy": ssl_policy,
        "fips_state": fips_state,
    }
    if gap is not None:
        content["gap"] = gap

    return Evidence.create(
        detector_id="aws.fips_ssl_policies_on_lb_listeners",
        ksis_evidenced=["KSI-SVC-VRI", "KSI-SVC-SNT"],
        controls_evidenced=["SC-13"],
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )


def _as_str(value: Any) -> str | None:
    """python-hcl2 occasionally returns strings wrapped in single-element lists."""
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value if isinstance(value, str) else None
