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

from efterlev.agents.base import (
    Agent,
    format_evidence_for_prompt,
    new_fence_nonce,
    parse_evidence_fence_ids,
)
from efterlev.agents.gap import KsiClassification
from efterlev.errors import AgentError
from efterlev.llm import LLMClient
from efterlev.models import AttestationDraft, Claim, Evidence, Indicator, ScanSummary
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
    # Slim summary of the scan that produced `evidence`. When the scan was
    # HCL-mode against a module-composed codebase, the per-KSI prompt
    # surfaces this so each narrative can reflect the coverage limitation
    # — `not_implemented` may mean "scanner couldn't see it" rather than
    # "the CSP doesn't have it." None when the agent is invoked directly
    # without a prior scan in the active store. Priority 0 (2026-04-27).
    scan_summary: ScanSummary | None = None


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
    """Narrative-synthesis agent for FRMR-style KSI attestations.

    Defaults to Sonnet 4.6 rather than Opus 4.7: the job is structured
    extractive writing against a tight format contract, not novel reasoning.
    Sonnet handles that at roughly 1/5th the cost per token with essentially
    no quality delta — 60 narratives per govnotes run drops from ~$4 to
    ~$1. Callers who want to force Opus (or Haiku for bulk drafts) can pass
    `model=...` explicitly.
    """

    name = "documentation_agent@0.1.0"
    system_prompt_path = "documentation_prompt.md"
    output_model = NarrativeOutput
    default_model = "claude-sonnet-4-6"

    def __init__(
        self,
        *,
        client: LLMClient | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(client=client, model=model)

    def run(
        self,
        input: DocumentationAgentInput,
        *,
        progress_callback: object | None = None,
    ) -> DocumentationReport:
        """Run the Documentation Agent over `input.classifications`.

        Pass `progress_callback` (a ProgressCallback-shaped object) to
        receive per-KSI completion events. The CLI uses
        `TerminalProgressCallback` to print `[idx/total] KSI-XXX ✓`
        for each narrative as it's drafted; tests pass a NoopProgressCallback
        (or omit it). The Documentation Agent processes one KSI per
        LLM call, so each completion is meaningful — the
        prior silent-7-minute behavior was specifically what users
        complained about.
        """
        from efterlev.cli.progress import NoopProgressCallback

        eligible, skipped = _select_classifications(input.classifications, input.only_ksi)
        callback = progress_callback if progress_callback is not None else NoopProgressCallback()

        attestations: list[KsiAttestation] = []
        store = get_active_store()
        total = len(eligible)

        for idx, clf in enumerate(eligible, start=1):
            indicator = input.indicators.get(clf.ksi_id)
            if indicator is None:
                # Classification references a KSI not in the loaded baseline.
                # Skip rather than crash — this is how baseline drift shows up.
                skipped.append(clf.ksi_id)
                callback.on_unit_complete(clf.ksi_id, idx, total, success=False)  # type: ignore[attr-defined]
                continue

            # Resolve evidence via the Gap classification's cited IDs rather
            # than re-filtering by `ksis_evidenced`. Rationale: the Gap Agent
            # is allowed to reason about cross-KSI relevance (e.g. citing a
            # CloudTrail record — detector-attributed to KSI-MLA-LET/OSM —
            # when classifying KSI-CMT-LMC, since modification events *are*
            # change-management-relevant). Using clf.evidence_ids here keeps
            # the Doc Agent's narrative coherent with the classification:
            # whatever evidence Gap cited, Doc shows. The Evidence's
            # ksis_evidenced stays as the detector's default attribution —
            # agents can extend it via reasoning.
            cited_ids = set(clf.evidence_ids)
            ksi_evidence = [ev for ev in input.evidence if ev.evidence_id in cited_ids]

            skeleton_result = generate_frmr_skeleton(
                GenerateFrmrSkeletonInput(
                    ksi_id=clf.ksi_id,
                    evidence=ksi_evidence,
                    baseline_id=input.baseline_id,
                    frmr_version=input.frmr_version,
                )
            )

            # Fresh nonce per KSI-draft LLM call — each invocation is its
            # own fence set. See DECISIONS 2026-04-22 Phase 2 post-review
            # fixup F.
            nonce = new_fence_nonce()
            user_message = _build_user_message(
                indicator,
                clf,
                ksi_evidence,
                nonce=nonce,
                scan_summary=input.scan_summary,
            )
            narrative_output, response, system_prompt = self._invoke_llm(user_message=user_message)
            assert isinstance(narrative_output, NarrativeOutput)

            _validate_cited_ids(
                narrative_output,
                fenced_prompt=system_prompt + "\n" + user_message,
                nonce=nonce,
                classification_evidence_ids=clf.evidence_ids,
            )

            final_draft = AttestationDraft(
                ksi_id=clf.ksi_id,
                baseline_id=input.baseline_id,
                frmr_version=input.frmr_version,
                mode="agent_drafted",
                citations=skeleton_result.draft.citations,
                # SPEC-57.2: skeleton already computed the union of
                # `Evidence.controls_evidenced` from the cited evidence;
                # carry it through to the artifact serializer.
                controls_evidenced=list(skeleton_result.draft.controls_evidenced),
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
            callback.on_unit_complete(clf.ksi_id, idx, total, success=True)  # type: ignore[attr-defined]

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
    *,
    nonce: str,
    scan_summary: ScanSummary | None = None,
) -> str:
    """Assemble the per-KSI user message: KSI metadata, classification, fenced evidence."""
    controls = ", ".join(indicator.controls) if indicator.controls else "(none in FRMR)"
    statement = indicator.statement or "(no statement in FRMR)"
    fenced = format_evidence_for_prompt(evidence, nonce=nonce)
    classification_block = json.dumps(
        {
            "ksi_id": classification.ksi_id,
            "status": classification.status,
            "rationale": classification.rationale,
            "evidence_ids": classification.evidence_ids,
        },
        indent=2,
    )

    summary_block = _format_scan_summary_block(scan_summary)

    return (
        "Draft an attestation narrative for the following KSI.\n\n" + summary_block + "## KSI\n\n"
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


def _format_scan_summary_block(scan_summary: ScanSummary | None) -> str:
    """Surface coverage limitations to the per-KSI Documentation prompt.

    When the underlying scan was thin-evidence due to module composition,
    the per-KSI narrative should reflect that — `not_implemented` may mean
    "scanner couldn't see it" rather than "the CSP doesn't have it." Plan-
    mode scans and HCL-mode against resource-only codebases produce no
    block; the prompt stays focused on the per-KSI evidence.
    """
    if scan_summary is None or not scan_summary.recommend_plan_json:
        return ""
    return (
        "## Scan coverage note\n\n"
        f"The underlying scan was HCL-mode and saw {scan_summary.module_calls} "
        f"`module` calls alongside {scan_summary.resources_parsed} root-level "
        "`resource` declarations. Detectors do not follow into upstream module "
        "sources, so resources defined inside those modules are invisible. "
        "When this KSI's classification is `not_implemented` AND the Gap Agent's "
        "rationale notes the absence is plausibly evidenceable from IaC, your "
        "narrative should explicitly acknowledge that the absence may reflect "
        "scanner coverage limits (specifically: HCL mode against module "
        "composition) rather than a real implementation gap. Recommend "
        "plan-JSON scanning where appropriate. Do NOT fabricate evidence; do "
        "NOT claim the CSP has implemented controls Efterlev has no evidence "
        "for. The honest framing is: 'this scan did not surface evidence; the "
        "absence may be a coverage gap, not a real gap.'\n\n"
    )


def _validate_cited_ids(
    output: NarrativeOutput,
    *,
    fenced_prompt: str,
    nonce: str,
    classification_evidence_ids: list[str],
) -> None:
    """Two-sided citation discipline:

    - Forbid fabrication (design call #3): every cited id must correspond to a
      real fence. Otherwise a model could invent `sha256:…` strings the human
      reader cannot trace back to evidence.
    - Forbid silent decitation: when the Gap Agent cited evidence for this
      KSI, the narrative MUST cite at least one of those ids. Otherwise a
      confidently-worded narrative can land in the persisted Claim with an
      empty `derived_from`, breaking the provenance graph and matching the
      same failure mode `KsiClassification._positive_status_requires_evidence`
      blocks on the Gap side. A `not_implemented` KSI with no Gap-cited
      evidence is the legitimate empty-cite path and is allowed through.
    """
    fenced_ids = parse_evidence_fence_ids(fenced_prompt, nonce=nonce)
    cited = set(output.cited_evidence_ids)
    fabricated = cited - fenced_ids
    if fabricated:
        raise AgentError(
            "documentation agent narrative cites evidence IDs not present in the prompt: "
            f"{sorted(fabricated)[:5]}. Prompt-injection guard refuses fabricated citations."
        )
    if classification_evidence_ids and not cited:
        raise AgentError(
            "documentation agent narrative has empty cited_evidence_ids despite the Gap "
            f"classification citing {len(classification_evidence_ids)} evidence id(s). "
            "Every narrative grounded in classified evidence must cite at least one "
            "of the underlying evidence ids — empty-cites would break the provenance graph."
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
