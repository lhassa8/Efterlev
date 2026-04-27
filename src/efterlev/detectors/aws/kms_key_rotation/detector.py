"""KMS key-rotation detector.

AWS KMS automatically rotates symmetric customer master keys every year
when `enable_key_rotation = true` on the `aws_kms_key` resource. The
attribute defaults to `false`, so a KMS key declared without it is
effectively un-rotated.

Asymmetric KMS keys (`customer_master_key_spec` starting with "RSA_",
"ECC_", "HMAC_", or "SM2") do NOT support automatic rotation —
`enable_key_rotation` is ignored. We record these as
`rotation_status="not_applicable"` so the Gap Agent doesn't conflate
them with genuine rotation gaps.

KSI mapping: KSI-SVC-ASM ("Automating Secret Management"). Statement:
"Automate management, protection, and regular rotation of digital keys,
certificates, and other secrets." SC-12 is in KSI-SVC-ASM's `controls`
array in FRMR 0.9.43-beta, and the KSI's statement explicitly names
"rotation of digital keys" — KMS key rotation is the canonical example.
The original 2026-04-21 design call left this `ksis=[]` because the
mapping wasn't immediately clear; the 2026-04-27 honesty pass (Priority
6 of `docs/v1-readiness-plan.md`) re-evaluated and confirmed
KSI-SVC-ASM is the right home.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_ASYMMETRIC_SPEC_PREFIXES = ("RSA_", "ECC_", "HMAC_", "SM2")


@detector(
    id="aws.kms_key_rotation",
    ksis=["KSI-SVC-ASM"],
    controls=["SC-12", "SC-12(2)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit key-rotation Evidence for every aws_kms_key found.

    Evidences (800-53):  SC-12 (Cryptographic Key Establishment and
                         Management). SC-12(2) (Symmetric Keys) when
                         rotation is confirmed on a symmetric CMK.
    Evidences (KSI):     KSI-SVC-ASM (Automating Secret Management).
                         FRMR 0.9.43-beta includes SC-12 in this KSI's
                         controls; the KSI statement explicitly names
                         "rotation of digital keys" which is what KMS
                         key rotation provides.
    Does NOT prove:      external HSM / BYOK posture, key-escrow or
                         multi-region replica key handling, whether
                         applications actually use the declared CMK (vs.
                         AWS-managed defaults), operational key-custody
                         practices, or runtime state of deployed keys.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type != "aws_kms_key":
            continue
        out.append(_emit_kms_evidence(r, now))
    return out


def _emit_kms_evidence(r: TerraformResource, now: datetime) -> Evidence:
    enable_rotation = r.body.get("enable_key_rotation")
    spec = r.body.get("customer_master_key_spec")
    is_asymmetric = isinstance(spec, str) and any(
        spec.startswith(p) for p in _ASYMMETRIC_SPEC_PREFIXES
    )

    content: dict[str, Any] = {
        "resource_type": r.type,
        "resource_name": r.name,
    }

    if is_asymmetric:
        content["rotation_status"] = "not_applicable"
        content["key_spec"] = spec
        content["note"] = (
            "Asymmetric KMS keys do not support automatic rotation; "
            "enable_key_rotation is ignored by AWS."
        )
        # For asymmetric keys, SC-12 still applies (the key is managed); the
        # enhancement (SC-12(2)) does not because it names symmetric rotation.
        controls = ["SC-12"]
    elif enable_rotation is True:
        content["rotation_status"] = "enabled"
        controls = ["SC-12", "SC-12(2)"]
    else:
        content["rotation_status"] = "disabled"
        content["gap"] = "enable_key_rotation not set to true on symmetric CMK"
        controls = ["SC-12"]

    return Evidence.create(
        detector_id="aws.kms_key_rotation",
        ksis_evidenced=["KSI-SVC-ASM"],
        controls_evidenced=controls,
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )
