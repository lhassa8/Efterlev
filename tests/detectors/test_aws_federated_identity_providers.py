"""Fixture-driven tests for `aws.federated_identity_providers`."""

from __future__ import annotations

from pathlib import Path

from efterlev.detectors.aws.federated_identity_providers.detector import detect
from efterlev.terraform import parse_terraform_file

DETECTOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "efterlev"
    / "detectors"
    / "aws"
    / "federated_identity_providers"
)


def _run_detector_on(path: Path) -> list:
    resources = parse_terraform_file(path)
    return detect(resources)


# --- should_match ----------------------------------------------------------


def test_oidc_provider_evidences_ia_2_and_ia_5_2() -> None:
    """OIDC provider — the canonical IRSA / GHA-OIDC pattern. Evidences
    IA-2 (Identification and Authentication — Organizational Users) AND
    IA-5(2) (Public Key-Based Authentication) since OIDC is PKI-token-based."""
    results = _run_detector_on(
        DETECTOR_DIR / "fixtures" / "should_match" / "oidc_github_actions.tf"
    )
    assert len(results) == 1
    ev = results[0]
    assert ev.detector_id == "aws.federated_identity_providers"
    assert ev.ksis_evidenced == ["KSI-IAM-APM"]
    assert set(ev.controls_evidenced) == {"IA-2", "IA-5(2)"}
    content = ev.content
    assert content["provider_kind"] == "oidc"
    assert content["resource_name"] == "github_actions"
    assert "token.actions.githubusercontent.com" in content["url"]
    assert content["client_id_count"] == 1
    assert content["thumbprint_count"] == 1
    assert content["federation_state"] == "declared"


def test_saml_provider_evidences_ia_2_only() -> None:
    """SAML — XML-signature-based, not PKI-token-based; conservatively claim
    IA-2 alone. The Gap Agent can reason about the partial-coverage."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_match" / "saml_okta.tf")
    assert len(results) == 1
    ev = results[0]
    assert ev.ksis_evidenced == ["KSI-IAM-APM"]
    # SAML evidences IA-2 alone, not IA-5(2).
    assert ev.controls_evidenced == ["IA-2"]
    content = ev.content
    assert content["provider_kind"] == "saml"
    assert content["name"] == "Okta"


# --- should_not_match ------------------------------------------------------


def test_no_providers_emits_nothing() -> None:
    """A codebase with IAM users/roles but no federated providers produces
    no evidence — the detector is anchored on provider declarations."""
    results = _run_detector_on(DETECTOR_DIR / "fixtures" / "should_not_match" / "no_providers.tf")
    assert results == []


def test_empty_resource_list() -> None:
    assert detect([]) == []


# --- mapping metadata ------------------------------------------------------


def test_detector_registration_metadata() -> None:
    from efterlev.detectors.base import get_registry

    spec = get_registry()["aws.federated_identity_providers"]
    assert spec.ksis == ("KSI-IAM-APM",)
    assert "IA-2" in spec.controls
    assert "IA-5(2)" in spec.controls
    assert spec.source == "terraform"
