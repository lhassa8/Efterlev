"""Remediation Agent — proposes a Terraform diff that would close a KSI gap.

Scope: one KSI per invocation. The agent receives the KSI metadata, the Gap
Agent classification, every Evidence record attributed to the KSI, and the
raw `.tf` file contents those evidence records reference. It returns a
`RemediationProposal` carrying a unified diff, a plain-English explanation,
and the set of cited evidence ids + source file paths.

Per CLAUDE.md's "What we are explicitly NOT building" list the agent never
opens a PR, applies the diff, or touches the repo. The CLI prints the diff;
a human engineer decides what to do with it.

Prompt-injection defense: both Evidence content and `.tf` file content are
attacker-controllable. Evidence goes through `format_evidence_for_prompt`
(XML-fenced on `evidence_id`); source files go through
`format_source_files_for_prompt` (XML-fenced on `path`). The post-generation
validator rejects any output that cites ids or paths not present as fences
in the prompt the model actually saw.

A `Claim(claim_type="remediation")` is persisted per proposal, with
`derived_from` listing the evidence ids the model cited. A user walking the
provenance chain from the rendered remediation back to the `.tf` line range
that triggered it finds: remediation → evidence → source_ref.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from efterlev.agents.base import (
    Agent,
    format_evidence_for_prompt,
    format_source_files_for_prompt,
    parse_evidence_fence_ids,
    parse_source_file_fence_paths,
)
from efterlev.agents.gap import KsiClassification
from efterlev.errors import AgentError
from efterlev.llm import DEFAULT_MODEL, LLMClient
from efterlev.models import Claim, Evidence, Indicator
from efterlev.provenance.context import get_active_store

RemediationStatus = Literal["proposed", "no_terraform_fix"]


class RemediationAgentInput(BaseModel):
    """Input to `RemediationAgent.run`. Exactly one KSI per invocation."""

    model_config = ConfigDict(frozen=True)

    indicator: Indicator
    classification: KsiClassification
    evidence: list[Evidence]
    source_files: dict[str, str] = Field(default_factory=dict)
    baseline_id: str
    frmr_version: str


class RemediationOutput(BaseModel):
    """Shape the LLM is asked to emit per the system prompt."""

    model_config = ConfigDict(frozen=True)

    diff: str
    explanation: str
    cited_evidence_ids: list[str] = Field(default_factory=list)
    cited_source_files: list[str] = Field(default_factory=list)


class RemediationProposal(BaseModel):
    """Structured output of the Remediation Agent."""

    model_config = ConfigDict(frozen=True)

    ksi_id: str
    status: RemediationStatus
    diff: str
    explanation: str
    cited_evidence_ids: list[str] = Field(default_factory=list)
    cited_source_files: list[str] = Field(default_factory=list)
    claim_record_id: str | None = None


class RemediationAgent(Agent):
    """LLM-backed Terraform-diff proposer for a single KSI gap."""

    name = "remediation_agent@0.1.0"
    system_prompt_path = "remediation_prompt.md"
    output_model = RemediationOutput

    def __init__(
        self,
        *,
        client: LLMClient | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        super().__init__(client=client, model=model)

    def run(self, input: RemediationAgentInput) -> RemediationProposal:
        user_message = _build_user_message(
            input.indicator, input.classification, input.evidence, input.source_files
        )
        # Larger max_tokens than the other agents: a unified diff for a
        # multi-resource change plus a 100-300 word explanation can run
        # 1-2k tokens in a plausible worst case.
        output, response, system_prompt = self._invoke_llm(
            user_message=user_message, max_tokens=8192
        )
        assert isinstance(output, RemediationOutput)

        _validate_citations(output, fenced_prompt=system_prompt + "\n" + user_message)

        status: RemediationStatus = "proposed" if output.diff.strip() else "no_terraform_fix"

        claim_record_id: str | None = None
        store = get_active_store()
        if store is not None:
            derived = list(output.cited_evidence_ids)
            claim = Claim.create(
                claim_type="remediation",
                content={
                    "ksi_id": input.indicator.id,
                    "status": status,
                    "diff": output.diff,
                    "explanation": output.explanation,
                    "cited_source_files": output.cited_source_files,
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
                metadata={"kind": "ksi_remediation", "ksi_id": input.indicator.id},
            )
            claim_record_id = record.record_id

        return RemediationProposal(
            ksi_id=input.indicator.id,
            status=status,
            diff=output.diff,
            explanation=output.explanation,
            cited_evidence_ids=list(output.cited_evidence_ids),
            cited_source_files=list(output.cited_source_files),
            claim_record_id=claim_record_id,
        )


def _build_user_message(
    indicator: Indicator,
    classification: KsiClassification,
    evidence: list[Evidence],
    source_files: dict[str, str],
) -> str:
    """Assemble the per-KSI user message: KSI, classification, fenced ev + sources."""
    controls = ", ".join(indicator.controls) if indicator.controls else "(none in FRMR)"
    statement = indicator.statement or "(no statement in FRMR)"
    fenced_evidence = format_evidence_for_prompt(evidence)
    fenced_sources = format_source_files_for_prompt(source_files)

    return (
        "Propose a Terraform remediation for the following KSI gap.\n\n"
        "## KSI\n\n"
        f"- ID: {indicator.id}\n"
        f"- Name: {indicator.name}\n"
        f"- Statement: {statement}\n"
        f"- Underlying 800-53 controls: {controls}\n\n"
        "## Gap Agent classification\n\n"
        f"- Status: {classification.status}\n"
        f"- Rationale: {classification.rationale}\n\n"
        "## Evidence records attributed to this KSI\n\n"
        + fenced_evidence
        + "\n\n## Terraform source files referenced by the evidence\n\n"
        + fenced_sources
        + "\n\nReturn JSON matching the schema in the system prompt. "
        "No prose outside the JSON, no code fences around the JSON, no commentary."
    )


def _validate_citations(output: RemediationOutput, *, fenced_prompt: str) -> None:
    """Enforce design call #3: every cited id/path must correspond to a real fence."""
    fenced_ids = parse_evidence_fence_ids(fenced_prompt)
    fenced_paths = parse_source_file_fence_paths(fenced_prompt)

    cited_ids = set(output.cited_evidence_ids)
    cited_paths = set(output.cited_source_files)

    fabricated_ids = cited_ids - fenced_ids
    fabricated_paths = cited_paths - fenced_paths

    if fabricated_ids:
        raise AgentError(
            "remediation agent cites evidence IDs not present in the prompt: "
            f"{sorted(fabricated_ids)[:5]}. "
            "Prompt-injection guard refuses fabricated citations."
        )
    if fabricated_paths:
        raise AgentError(
            "remediation agent cites source file paths not present in the prompt: "
            f"{sorted(fabricated_paths)[:5]}. "
            "Prompt-injection guard refuses fabricated citations."
        )
