"""Reasoning agents (Gap, Documentation, Remediation).

Each agent consumes Evidence and/or internal artifacts, sends them through
an LLM using the conventions in `efterlev.agents.base`, and returns a
typed artifact on our internal model. Every agent emits provenance records
for both the model invocation and each resulting `Claim`.
"""

from __future__ import annotations

from efterlev.agents.base import Agent, format_evidence_for_prompt, parse_evidence_fence_ids
from efterlev.agents.documentation import (
    DocumentationAgent,
    DocumentationAgentInput,
    DocumentationReport,
    KsiAttestation,
    NarrativeOutput,
    reconstruct_classifications_from_store,
)
from efterlev.agents.gap import (
    GapAgent,
    GapAgentInput,
    GapReport,
    KsiClassification,
    UnmappedFinding,
)

__all__ = [
    "Agent",
    "DocumentationAgent",
    "DocumentationAgentInput",
    "DocumentationReport",
    "GapAgent",
    "GapAgentInput",
    "GapReport",
    "KsiAttestation",
    "KsiClassification",
    "NarrativeOutput",
    "UnmappedFinding",
    "format_evidence_for_prompt",
    "parse_evidence_fence_ids",
    "reconstruct_classifications_from_store",
]
