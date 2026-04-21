"""Gap Agent — classify each baseline KSI as implemented / partial / not_implemented / NA.

The Gap Agent is v0's first agent. It consumes:

  - the baseline's list of `Indicator`s (the set of KSIs to classify), and
  - the set of `Evidence` records produced by `scan_terraform` so far,

and returns a `GapReport` with one `KsiClassification` per baseline KSI plus
a bucket of `UnmappedFinding`s for evidence records whose `ksis_evidenced=[]`
(per DECISIONS 2026-04-21 design call #1 — SC-28 lives here).

Trust boundary: evidence content is attacker-controllable at the input layer.
Every evidence record this agent shows the model goes through
`format_evidence_for_prompt` which XML-fences it (DECISIONS 2026-04-21
design call #3). The `validate_cited_ids` step below rejects any output that
cites an evidence id the model did not actually see in the prompt.

Every classification becomes a `Claim(claim_type="classification")` with
`derived_from=[evidence_ids]`, persisted into the active ProvenanceStore so
the Documentation Agent (Phase 3 downstream) can walk from a drafted
attestation back to the evidence that supported it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from efterlev.agents.base import Agent, format_evidence_for_prompt, parse_evidence_fence_ids
from efterlev.errors import AgentError
from efterlev.llm import DEFAULT_MODEL, LLMClient
from efterlev.models import Claim, Evidence, Indicator
from efterlev.provenance.context import get_active_store

GapStatus = Literal["implemented", "partial", "not_implemented", "not_applicable"]


class GapAgentInput(BaseModel):
    """Input to `GapAgent.run`."""

    model_config = ConfigDict(frozen=True)

    indicators: list[Indicator]
    evidence: list[Evidence]


class KsiClassification(BaseModel):
    """One KSI's classification as returned by the Gap Agent."""

    model_config = ConfigDict(frozen=True)

    ksi_id: str
    status: GapStatus
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)


class UnmappedFinding(BaseModel):
    """An evidence record whose `ksis_evidenced=[]` — no KSI attribution in FRMR."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    controls: list[str]
    note: str


class GapReport(BaseModel):
    """Structured output of the Gap Agent — both persisted and returned to CLI.

    `claim_record_ids` is a parallel list to `ksi_classifications` holding the
    `ProvenanceRecord.record_id` each classification was persisted under — the
    id the user passes to `efterlev provenance show` to walk the chain. These
    are distinct from internal Claim content-hashes (which are the
    `Claim.claim_id`s); only the record_id walks the provenance graph.
    """

    model_config = ConfigDict(frozen=True)

    ksi_classifications: list[KsiClassification]
    unmapped_findings: list[UnmappedFinding]
    claim_record_ids: list[str] = Field(default_factory=list)


class GapAgent(Agent):
    """LLM-backed KSI classifier, grounded in deterministic scanner evidence."""

    name = "gap_agent@0.1.0"
    system_prompt_path = "gap_prompt.md"
    output_model = GapReport

    def __init__(
        self,
        *,
        client: LLMClient | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        super().__init__(client=client, model=model)

    def run(self, input: GapAgentInput) -> GapReport:
        mapped_evidence, unmapped_evidence = _split_mapped_unmapped(input.evidence)
        user_message = _build_user_message(input.indicators, mapped_evidence, unmapped_evidence)

        report, response, system_prompt = self._invoke_llm(user_message=user_message)
        assert isinstance(report, GapReport)  # type narrowing

        _validate_cited_ids(report, fenced_prompt=system_prompt + "\n" + user_message)

        # Persist one Claim per KSI classification, linking back to the
        # evidence IDs the model cited. `cited_evidence_ids` are already in
        # `sha256:<hex>` form (the fence id format) which matches evidence
        # record_ids exactly, so Claim.derived_from stores them as-is — no
        # prefix translation at the boundary.
        record_ids: list[str] = []
        store = get_active_store()
        for clf in report.ksi_classifications:
            claim = Claim.create(
                claim_type="classification",
                content={
                    "ksi_id": clf.ksi_id,
                    "status": clf.status,
                    "rationale": clf.rationale,
                },
                confidence="medium",
                derived_from=list(clf.evidence_ids),
                model=response.model,
                prompt_hash=response.prompt_hash,
            )
            if store is not None:
                record = store.write_record(
                    payload=claim.model_dump(mode="json"),
                    record_type="claim",
                    derived_from=list(clf.evidence_ids),
                    agent=self.name,
                    model=response.model,
                    prompt_hash=response.prompt_hash,
                    metadata={"kind": "ksi_classification", "ksi_id": clf.ksi_id},
                )
                record_ids.append(record.record_id)

        return report.model_copy(update={"claim_record_ids": record_ids})


def _split_mapped_unmapped(
    evidence: list[Evidence],
) -> tuple[list[Evidence], list[Evidence]]:
    """Bucket evidence by whether it carries any KSI attribution."""
    mapped: list[Evidence] = []
    unmapped: list[Evidence] = []
    for ev in evidence:
        if ev.ksis_evidenced:
            mapped.append(ev)
        else:
            unmapped.append(ev)
    return mapped, unmapped


def _build_user_message(
    indicators: list[Indicator],
    mapped_evidence: list[Evidence],
    unmapped_evidence: list[Evidence],
) -> str:
    """Assemble the single user message with fenced evidence blocks."""
    ksi_lines: list[str] = []
    for ind in indicators:
        statement = ind.statement or "(no statement in FRMR)"
        ksi_lines.append(f"- {ind.id} — {ind.name}: {statement}")

    fenced_mapped = format_evidence_for_prompt(mapped_evidence)
    fenced_unmapped = format_evidence_for_prompt(unmapped_evidence)

    return (
        "Classify the following KSIs from the loaded FedRAMP 20x baseline.\n\n"
        "## KSIs to classify\n\n"
        + "\n".join(ksi_lines)
        + "\n\n## Evidence attached to one or more KSIs\n\n"
        + fenced_mapped
        + "\n\n## Evidence with no KSI attribution (unmapped)\n\n"
        + fenced_unmapped
        + "\n\nReturn JSON matching the schema in the system prompt. "
        "No prose, no code fences, no commentary."
    )


def _validate_cited_ids(report: GapReport, *, fenced_prompt: str) -> None:
    """Enforce design call #3: every cited id must correspond to a real fence."""
    fenced_ids = parse_evidence_fence_ids(fenced_prompt)
    cited: set[str] = set()
    for clf in report.ksi_classifications:
        cited.update(clf.evidence_ids)
    for um in report.unmapped_findings:
        cited.add(um.evidence_id)

    fabricated = cited - fenced_ids
    if fabricated:
        raise AgentError(
            f"gap agent output cites evidence IDs not present in the prompt: "
            f"{sorted(fabricated)[:5]}. Prompt-injection guard refuses fabricated citations."
        )
