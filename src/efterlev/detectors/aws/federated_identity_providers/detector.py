"""Federated-identity-providers detector.

Looks for `aws_iam_openid_connect_provider` and `aws_iam_saml_provider`
resources. Each declared provider is evidence the customer is using
federated identity — OIDC for service-account / workload identity (the
canonical IRSA / GitHub-Actions-OIDC / Workload-Identity-Federation
pattern), SAML for human users authenticated through an enterprise IdP.
KSI-IAM-APM ("Adopting Passwordless Methods") asks the customer to use
passwordless authentication where feasible; federated identity IS
passwordless authentication for the relying party.

A workload that has IRSA configured is authenticating its compute (EKS
pods) without long-lived AWS access keys — exactly the IAM-APM pattern
FedRAMP wants. A SAML provider declared at the AWS account level means
human users come in via the IdP rather than IAM-username/password.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-IAM-APM lists `ia-2.1`, `ia-2.2`, `ia-2.8`, `ia-5.1`, `ia-5.2`,
    `ia-5.6`, `ia-6` in its `controls` array. This detector evidences
    IA-2 (Identification and Authentication — Organizational Users) at
    the structural level and IA-5(2) (Public Key-Based Authentication)
    when an OIDC provider is declared (OIDC's signature verification
    IS PKI-based).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource


@detector(
    id="aws.federated_identity_providers",
    ksis=["KSI-IAM-APM"],
    controls=["IA-2", "IA-5(2)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one Evidence per declared OIDC or SAML provider.

    Evidences (800-53):  IA-2 (Identification and Authentication —
                         Organizational Users) at the declaration layer.
                         IA-5(2) (Public Key-Based Authentication) when
                         the provider is OIDC (OIDC tokens are signed
                         with the IdP's PKI).
    Evidences (KSI):     KSI-IAM-APM (Adopting Passwordless Methods).
    Does NOT prove:      that the IdP itself enforces phishing-resistant
                         MFA at login time (that's KSI-IAM-MFA territory
                         and lives in IdP configuration outside AWS),
                         that all human or service principals use the
                         provider (some may still authenticate with
                         long-lived keys), or that the provider's
                         thumbprint/signing-key rotation is automated.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for r in resources:
        if r.type == "aws_iam_openid_connect_provider":
            out.append(_emit_oidc_evidence(r, now))
        elif r.type == "aws_iam_saml_provider":
            out.append(_emit_saml_evidence(r, now))

    return out


def _emit_oidc_evidence(r: TerraformResource, now: datetime) -> Evidence:
    """Characterize one OIDC provider declaration."""
    url = _coerce_str(r.body.get("url"))
    client_ids = r.body.get("client_id_list")
    thumbprints = r.body.get("thumbprint_list")

    content: dict[str, Any] = {
        "resource_type": r.type,
        "resource_name": r.name,
        "provider_kind": "oidc",
        "url": url,
        "client_id_count": _list_len(client_ids),
        "thumbprint_count": _list_len(thumbprints),
        "federation_state": "declared",
    }
    return Evidence.create(
        detector_id="aws.federated_identity_providers",
        ksis_evidenced=["KSI-IAM-APM"],
        controls_evidenced=["IA-2", "IA-5(2)"],
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )


def _emit_saml_evidence(r: TerraformResource, now: datetime) -> Evidence:
    """Characterize one SAML provider declaration. SAML evidences IA-2 but
    not IA-5(2): SAML is XML-signature-based but the FRMR mapping for
    IA-5(2) reads as PKI-token-based (OIDC); we conservatively claim
    IA-2 only and let the Gap Agent reason about the partial-coverage."""
    name = _coerce_str(r.body.get("name"))
    metadata_url = _coerce_str(r.body.get("saml_metadata_document"))

    content: dict[str, Any] = {
        "resource_type": r.type,
        "resource_name": r.name,
        "provider_kind": "saml",
        "name": name,
        "metadata_inline": metadata_url is not None and len(metadata_url) > 0,
        "federation_state": "declared",
    }
    return Evidence.create(
        detector_id="aws.federated_identity_providers",
        ksis_evidenced=["KSI-IAM-APM"],
        controls_evidenced=["IA-2"],
        source_ref=r.source_ref,
        content=content,
        timestamp=now,
    )


def _list_len(value: Any) -> int:
    """python-hcl2 yields list-of-strings as `[["x", "y"]]` or `["x"]`. Flatten + count."""
    if value is None:
        return 0
    if isinstance(value, str):
        return 1
    if isinstance(value, list):
        flat: list[str] = []
        for item in value:
            if isinstance(item, list):
                flat.extend(str(x) for x in item)
            elif isinstance(item, str):
                flat.append(item)
        return len(flat)
    return 0


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
