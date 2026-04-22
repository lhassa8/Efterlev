"""Evidence Manifest loader tests.

Covers the file-discovery + parse + validate path in
`efterlev.manifests.loader`. The primitive that consumes the loader is
tested separately in `test_load_evidence_manifests_primitive.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from efterlev.errors import ManifestError
from efterlev.manifests import discover_manifest_files, load_manifest_file

_VALID_MANIFEST = """
ksi: KSI-AFR-FSI
name: FedRAMP Security Inbox
evidence:
  - type: attestation
    statement: security@example.com monitored 24/7 by SOC team.
    attested_by: vp-security@example.com
    attested_at: 2026-04-15
    reviewed_at: 2026-04-15
    next_review: 2026-10-15
    supporting_docs:
      - ./policies/security-inbox-sop.pdf
      - https://wiki.example.com/soc/security-inbox
"""


def test_discover_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    assert discover_manifest_files(tmp_path / "no-such") == []


def test_discover_returns_sorted_yml_and_yaml(tmp_path: Path) -> None:
    (tmp_path / "b.yml").write_text("ksi: KSI-1\nevidence: []\n")
    (tmp_path / "a.yaml").write_text("ksi: KSI-2\nevidence: []\n")
    (tmp_path / "not-a-manifest.txt").write_text("ignore me")
    found = discover_manifest_files(tmp_path)
    assert [p.name for p in found] == ["a.yaml", "b.yml"]


def test_load_valid_manifest_parses_every_field(tmp_path: Path) -> None:
    path = tmp_path / "security-inbox.yml"
    path.write_text(_VALID_MANIFEST)
    manifest = load_manifest_file(path)
    assert manifest.ksi == "KSI-AFR-FSI"
    assert manifest.name == "FedRAMP Security Inbox"
    assert len(manifest.evidence) == 1
    attestation = manifest.evidence[0]
    assert attestation.type == "attestation"
    assert attestation.attested_by == "vp-security@example.com"
    assert attestation.attested_at.isoformat() == "2026-04-15"
    assert attestation.next_review is not None
    assert attestation.next_review.isoformat() == "2026-10-15"
    assert len(attestation.supporting_docs) == 2


def test_load_manifest_without_optional_fields_is_fine(tmp_path: Path) -> None:
    path = tmp_path / "minimal.yml"
    path.write_text(
        "ksi: KSI-AFR-FSI\n"
        "evidence:\n"
        "  - statement: a statement\n"
        "    attested_by: me@example.com\n"
        "    attested_at: 2026-04-15\n"
    )
    manifest = load_manifest_file(path)
    assert manifest.name is None
    assert manifest.evidence[0].reviewed_at is None
    assert manifest.evidence[0].next_review is None
    assert manifest.evidence[0].supporting_docs == []


def test_load_raises_on_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "broken.yml"
    path.write_text("ksi: KSI-AFR-FSI\nevidence: [\n")  # unterminated list
    with pytest.raises(ManifestError, match="not valid YAML"):
        load_manifest_file(path)


def test_load_raises_on_top_level_list(tmp_path: Path) -> None:
    path = tmp_path / "list.yml"
    path.write_text("- ksi: KSI-AFR-FSI\n  evidence: []\n")
    with pytest.raises(ManifestError, match="must be a YAML mapping"):
        load_manifest_file(path)


def test_load_raises_on_unknown_key(tmp_path: Path) -> None:
    # `extra="forbid"` catches typos like `attester` vs `attested_by` before
    # a silent attribution bug lands in the provenance store.
    path = tmp_path / "typo.yml"
    path.write_text(
        "ksi: KSI-AFR-FSI\n"
        "evidence:\n"
        "  - statement: a statement\n"
        "    attester: me@example.com\n"  # typo
        "    attested_at: 2026-04-15\n"
    )
    with pytest.raises(ManifestError, match="failed schema validation"):
        load_manifest_file(path)


def test_load_raises_on_missing_required_field(tmp_path: Path) -> None:
    path = tmp_path / "incomplete.yml"
    path.write_text(
        "ksi: KSI-AFR-FSI\n"
        "evidence:\n"
        "  - statement: a statement\n"
        # missing attested_by and attested_at
        "    next_review: 2026-10-15\n"
    )
    with pytest.raises(ManifestError, match="failed schema validation"):
        load_manifest_file(path)


def test_load_raises_on_malformed_date(tmp_path: Path) -> None:
    path = tmp_path / "bad-date.yml"
    path.write_text(
        "ksi: KSI-AFR-FSI\n"
        "evidence:\n"
        "  - statement: a statement\n"
        "    attested_by: me@example.com\n"
        "    attested_at: not-a-date\n"
    )
    with pytest.raises(ManifestError, match="failed schema validation"):
        load_manifest_file(path)


def test_load_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="failed to read manifest"):
        load_manifest_file(tmp_path / "no-such.yml")
