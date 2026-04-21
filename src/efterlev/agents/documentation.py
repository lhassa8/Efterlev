"""Documentation Agent — drafts narrative attestations grounded in scanner evidence.

Wraps `generate_frmr_skeleton` (deterministic) + an LLM narrative call + final
`AttestationDraft(mode="agent_drafted")` assembly, one KSI at a time.

Per DECISIONS 2026-04-21 design call #2 the deterministic half is the
`generate_frmr_skeleton` primitive (already landed separately); the narrative
fill lives here because the LLM client belongs to the agent, not the
primitive layer. The composition step (skeleton + status + narrative →
agent_drafted draft) is collapsed into the agent rather than being a
separate "generative primitive" — it's a few lines of assembly, not
independently reusable enough to justify its own `@primitive` surface. See
DECISIONS 2026-04-21 "Documentation Agent composition scope" for the
rationale.

Every drafted attestation emits a `Claim(claim_type="narrative")` into the
active provenance store, with `derived_from` pointing at the evidence IDs
the model cited. A human-review walker can follow the chain from the
rendered attestation to the underlying .tf file lines without re-running
the agent.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from efterlev.agents.base import Agent, format_evidence_for_prompt, parse_evidence_fence_ids
from efterlev.agents.gap import KsiClassification
from efterlev.errors import AgentError
from efterlev.llm import DEFAULT_MODEL, LLMClient
from efterlev.models import AttestationDraft, Claim, Evidence, Indicator
from efterlev.primitives.generate import GenerateFrmrSkeletonInput, generate_frmr_skeleton
from efterlev.provenance.context import get_active_store


class DocumentationAgentInput(BaseModel):
    """Input to `DocumentationAgent.run`."""

    model_config = ConfigDict(frozen=True)

    indicators: dict[str, Indicator]
    evidence: list[Evidence]
    classifications: list[KsiClassification]
    baseline_id: str
    frmr_version: str
    only_ksi: str | None = None


class NarrativeOutput(BaseModel):
    """Shape the LLM is asked to emit — narrative + flat list of cited IDs."""

    model_config = ConfigDict(frozen=True)

    narrative: str
    cited_evidence_ids: list[str] = Field(default_factory=list)


class KsiAttestation(BaseModel):
    """One drafted attestation paired with its provenance record id."""

    model_config = ConfigDict(frozen=True)

    draft: AttestationDraft
    claim_record_id: str | None = None


class DocumentationReport(BaseModel):
    """Structured output of the Documentation Agent."""

    model_config = ConfigDict(frozen=True)

    attestations: list[KsiAttestation] = Field(default_factory=list)
    skipped_ksi_ids: list[str] = Field(default_factory=list)


class DocumentationAgent(Agent):
    """Narrative-synthesis agent for FRMR-style KSI attestations."""

    name = "documentation_agent@0.1.0"
    system_prompt_path = "documentation_prompt.md"
    output_model = NarrativeOutput

    def __init__(
        self,
        *,
        client: LLMClient | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        super().__init__(client=client, model=model)

    def run(self, input: DocumentationAgentInput) -> DocumentationReport:
        eligible, skipped = _select_classifications(input.classifications, input.only_ksi)

        attestations: list[KsiAttestation] = []
        store = get_active_store()

        for clf in eligible:
            indicator = input.indicators.get(clf.ksi_id)
            if indicator is None:
                # Classification references a KSI not in the loaded baseline.
                # Skip rather than crash — this is how baseline drift shows up.
                skipped.append(clf.ksi_id)
                continue

            ksi_evidence = [ev for ev in input.evidence if clf.ksi_id in ev.ksis_evidenced]

            skeleton_result = generate_frmr_skeleton(
                GenerateFrmrSkeletonInput(
                    ksi_id=clf.ksi_id,
                    evidence=ksi_evidence,
                    baseline_id=input.baseline_id,
                    frmr_version=input.frmr_version,
                )
            )

            user_message = _build_user_message(indicator, clf, ksi_evidence)
            narrative_output, response, system_prompt = self._invoke_llm(user_message=user_message)
            assert isinstance(narrative_output, NarrativeOutput)

            _validate_cited_ids(narrative_output, fenced_prompt=system_prompt + "\n" + user_message)

            final_draft = AttestationDraft(
                ksi_id=clf.ksi_id,
                baseline_id=input.baseline_id,
                frmr_version=input.frmr_version,
                mode="agent_drafted",
                citations=skeleton_result.draft.citations,
                status=clf.status if clf.status != "not_applicable" else None,
                narrative=narrative_output.narrative,
            )

            claim_record_id: str | None = None
            if store is not None:
                # cited_evidence_ids already carry the `sha256:` prefix (fence
                # id format == evidence_id format == record_id format).
                derived = list(narrative_output.cited_evidence_ids)
                claim = Claim.create(
                    claim_type="narrative",
                    content={
                        "ksi_id": clf.ksi_id,
                        "narrative": narrative_output.narrative,
                        "status": clf.status,
                    },
                    confidence="medium",
                    derived_from=derived,
                    model=response.model,
                    prompt_hash=response.prompt_hash,
                )
                record = store.write_record(
                    payload=claim.model_dump(mode="json"),
                    record_type="claim",
                    derived_from=derived,
                    agent=self.name,
                    model=response.model,
                    prompt_hash=response.prompt_hash,
                    metadata={"kind": "ksi_attestation", "ksi_id": clf.ksi_id},
                )
                claim_record_id = record.record_id

            attestations.append(KsiAttestation(draft=final_draft, claim_record_id=claim_record_id))

        return DocumentationReport(attestations=attestations, skipped_ksi_ids=skipped)


def _select_classifications(
    classifications: list[KsiClassification], only_ksi: str | None
) -> tuple[list[KsiClassification], list[str]]:
    """Partition classifications into eligible (draft these) and skipped.

    Default: skip `not_applicable` only. A user explicitly naming a single
    KSI with `--ksi` overrides the NA filter — if they ask for it by name,
    draft it anyway.
    """
    eligible: list[KsiClassification] = []
    skipped: list[str] = []
    for clf in classifications:
        if only_ksi is not None:
            if clf.ksi_id == only_ksi:
                eligible.append(clf)
            else:
                skipped.append(clf.ksi_id)
            continue
        if clf.status == "not_applicable":
            skipped.append(clf.ksi_id)
        else:
            eligible.append(clf)
    return eligible, skipped


def _build_user_message(
    indicator: Indicator,
    classification: KsiClassification,
    evidence: list[Evidence],
) -> str:
    """Assemble the per-KSI user message: KSI metadata, classification, fenced evidence."""
    controls = ", ".join(indicator.controls) if indicator.controls else "(none in FRMR)"
    statement = indicator.statement or "(no statement in FRMR)"
    fenced = format_evidence_for_prompt(evidence)
    classification_block = json.dumps(
        {
            "ksi_id": classification.ksi_id,
            "status": classification.status,
            "rationale": classification.rationale,
            "evidence_ids": classification.evidence_ids,
        },
        indent=2,
    )

    return (
        "Draft an attestation narrative for the following KSI.\n\n"
        "## KSI\n\n"
        f"- ID: {indicator.id}\n"
        f"- Name: {indicator.name}\n"
        f"- Statement: {statement}\n"
        f"- Underlying 800-53 controls: {controls}\n\n"
        "## Gap Agent classification\n\n"
        + classification_block
        + "\n\n## Evidence records attributed to this KSI\n\n"
        + fenced
        + "\n\nReturn JSON matching the schema in the system prompt. "
        "No prose, no code fences, no commentary."
    )


def _validate_cited_ids(output: NarrativeOutput, *, fenced_prompt: str) -> None:
    """Enforce design call #3: every cited id must correspond to a real fence."""
    fenced_ids = parse_evidence_fence_ids(fenced_prompt)
    cited = set(output.cited_evidence_ids)
    fabricated = cited - fenced_ids
    if fabricated:
        raise AgentError(
            "documentation agent narrative cites evidence IDs not present in the prompt: "
            f"{sorted(fabricated)[:5]}. Prompt-injection guard refuses fabricated citations."
        )


def reconstruct_classifications_from_store(
    claim_records: list[tuple[str, dict[str, Any], dict[str, Any]]],
) -> list[KsiClassification]:
    """Rebuild `KsiClassification`s from `iter_claims_by_metadata_kind('ksi_classification')`.

    Used by the CLI to hand the agent the Gap Agent's prior output without
    re-running classification. Malformed records are skipped rather than
    raising — a single bad row shouldn't kill the whole `agent document`
    run when the rest of the classifications are usable.

    Evidence IDs on the rebuilt classifications are the `sha256:<hex>` fence
    format (== evidence_id == record_id) so the Documentation Agent's
    fence-citation validator matches end-to-end.
    """
    results: list[KsiClassification] = []
    for _record_id, metadata, payload in claim_records:
        ksi_id = metadata.get("ksi_id")
        content = payload.get("content")
        if not isinstance(ksi_id, str) or not isinstance(content, dict):
            continue
        status = content.get("status")
        rationale = content.get("rationale", "")
        if not isinstance(status, str):
            continue
        derived = payload.get("derived_from") or []
        try:
            results.append(
                KsiClassification(
                    ksi_id=ksi_id,
                    status=status,  # type: ignore[arg-type]
                    rationale=rationale,
                    evidence_ids=list(derived),
                )
            )
        except ValidationError:
            continue
    return results
