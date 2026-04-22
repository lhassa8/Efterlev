"""Evidence Manifest — human-attested procedural evidence declared in-repo.

Evidence Manifests are YAML files under `.efterlev/manifests/*.yml` where a
customer declares attestations for procedural controls that the Terraform
scanner can't see (e.g., the existence of a monitored security inbox with a
runbook, a personnel screening policy, an incident response process). Each
attestation names the KSI it satisfies, the statement, who attested it,
when, and when it must be re-reviewed.

Manifest attestations produce `Evidence` records (not `Claim`s) because
they are human-signed facts — deterministic at load time and citable
without LLM involvement. The evidence-vs-claims discipline treats scanner-
derived and manifest-declared Evidence as two instances of the same class;
the source distinction is carried via `Evidence.detector_id == "manifest"`.
Renderers and the Gap Agent's prompt see the distinction and can treat the
two kinds differently; the store-level flow is identical.

See DECISIONS 2026-04-22 "Evidence Manifests: human-attested procedural
evidence as a new Evidence source" for the full design call.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AttestationType = Literal["attestation"]


class ManifestAttestation(BaseModel):
    """A single human-signed attestation inside a manifest file.

    Each attestation produces one `Evidence` record at load time. The
    deterministic `evidence_id` is derived from the full content block,
    so editing the `statement` text produces a new evidence record (the
    old record remains in the append-only provenance store).

    `extra="forbid"` is load-bearing: an unknown YAML key is almost always
    a typo (`attester` vs `attested_by`) and silently accepting it would
    swallow a mistake that affects attribution. Raise loudly instead.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: AttestationType = "attestation"
    statement: str
    attested_by: str
    attested_at: date
    reviewed_at: date | None = None
    next_review: date | None = None
    supporting_docs: list[str] = Field(default_factory=list)


class EvidenceManifest(BaseModel):
    """One `.efterlev/manifests/*.yml` file's parsed contents.

    A manifest binds to exactly one KSI. A customer that wants to attest to
    multiple KSIs with the same underlying process writes multiple files
    (cheap: copy the YAML, change `ksi:`). Keeping the file-to-KSI
    relationship one-to-one makes downstream filtering, provenance walking,
    and staleness reporting trivial.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ksi: str
    name: str | None = None
    evidence: list[ManifestAttestation] = Field(default_factory=list)
