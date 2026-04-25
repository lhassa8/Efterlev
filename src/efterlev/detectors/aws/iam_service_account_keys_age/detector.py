"""IAM service-account access-keys detector.

Inspects `aws_iam_access_key` resources. Long-lived access keys for
IAM users without a console password are an anti-pattern; AWS
recommends rotating them within 90 days. Terraform doesn't carry the
key creation date so we evidence *presence* of the access key plus
a cross-reference flag indicating whether the user has a
`aws_iam_user_login_profile` (i.e., human user with console access)
or not (service-account-shaped).

KSI mapping per FRMR 0.9.43-beta:
  - KSI-IAM-SNU (Securing Non-User Authentication) lists ia-5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.iam_service_account_keys_age",
    ksis=["KSI-IAM-SNU"],
    controls=["IA-2", "IA-5"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit Evidence per access key, distinguishing service vs human user.

    Evidences (800-53):  IA-2 (Identification and Authentication),
                         IA-5 (Authenticator Management).
    Evidences (KSI):     KSI-IAM-SNU (Securing Non-User Authentication).
    Does NOT prove:      the key's age (not visible from IaC); whether
                         the key is actually used; whether the user has
                         MFA enforced (the existing
                         `aws.mfa_required_on_iam_policies` detector
                         handles MFA evidence).
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    # Index login profiles by user reference for cross-checking.
    login_profiles: set[str] = set()
    for r in resources:
        if r.type != "aws_iam_user_login_profile":
            continue
        user = _coerce_str(r.body.get("user"))
        if user:
            login_profiles.add(user)

    for r in resources:
        if r.type != "aws_iam_access_key":
            continue
        out.append(_emit_access_key_evidence(r, login_profiles, now))

    return out


def _emit_access_key_evidence(
    r: TerraformResource,
    login_profiles: set[str],
    now: datetime,
) -> Evidence:
    user_ref = _coerce_str(r.body.get("user")) or ""
    has_console = any(
        # Match on substring — Terraform refs like `aws_iam_user.dev.name`
        # render as such literals; we treat any login profile referencing
        # this user-string as evidence of human-user-ness.
        profile_user in user_ref or user_ref in profile_user
        for profile_user in login_profiles
    )
    profile_kind = "human_user_with_keys" if has_console else "service_account"

    return Evidence.create(
        detector_id="aws.iam_service_account_keys_age",
        ksis_evidenced=["KSI-IAM-SNU"],
        controls_evidenced=["IA-2", "IA-5"],
        source_ref=r.source_ref,
        content={
            "resource_type": "aws_iam_access_key",
            "resource_name": r.name,
            "user_ref": user_ref,
            "profile_kind": profile_kind,
            "rotation_visibility": "iac_cannot_show_age",
            "gap": (
                "long-lived IAM access key declared in IaC; rotation age "
                "is not visible from Terraform alone"
            ),
        },
        timestamp=now,
    )


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
