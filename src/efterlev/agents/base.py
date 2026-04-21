"""Shared agent scaffolding: evidence fencing, prompt loading, base class.

Three things live here:

  1. `format_evidence_for_prompt(evidence)` — the *only* way agents should
     embed Evidence content into a prompt. Each record is wrapped in an
     `<evidence id="sha256:...">...</evidence>` fence per DECISIONS
     2026-04-21 design call #3. No agent assembles prompts by hand.

  2. `parse_evidence_fence_ids(prompt)` — recovers the set of fence IDs
     actually present in a prompt, used by the post-generation validator
     to confirm every cited evidence ID maps to a real fence.

  3. `Agent` — abstract base. Subclasses declare `name`, `system_prompt_path`,
     and an `output_model` pydantic class; `Agent.run(...)` loads the
     prompt, calls the LLM via the injected client, parses + validates the
     response, and emits a provenance record for the model invocation.
     Subclasses build the user message(s) and transform the parsed JSON
     into the final typed artifact.

Evidence fencing is mandatory. Any agent that assembles its own evidence
strings bypasses the prompt-injection defense that the whole generative
layer depends on.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC
from pathlib import Path

from pydantic import BaseModel, ValidationError

from efterlev.errors import AgentError
from efterlev.llm import DEFAULT_MODEL, LLMClient, LLMMessage, LLMResponse, get_default_client
from efterlev.models import Evidence
from efterlev.provenance.context import get_active_store

log = logging.getLogger(__name__)


_FENCE_RE = re.compile(r'<evidence id="([^"]+)">')


def format_evidence_for_prompt(evidence: list[Evidence]) -> str:
    """Return a prompt fragment wrapping each Evidence in an XML fence.

    Fence format: `<evidence id="<evidence_id>">` + the JSON-serialized content
    dict + `</evidence>`. The `evidence_id` already carries the `sha256:`
    prefix (see `models._hashing.compute_content_id`), so the rendered fence
    looks like `<evidence id="sha256:abc…">` and matches the provenance
    record_id format exactly. An LLM that cites the fence id is citing a
    provenance-walkable id directly, no prefix translation at the boundary.

    Records are emitted in input order; the downstream validator parses IDs
    by regex and only cares about uniqueness.
    """
    if not evidence:
        return "(no evidence records)"

    blocks: list[str] = []
    for ev in evidence:
        payload = {
            "detector_id": ev.detector_id,
            "ksis_evidenced": ev.ksis_evidenced,
            "controls_evidenced": ev.controls_evidenced,
            "source_ref": ev.source_ref.model_dump(mode="json"),
            "content": ev.content,
        }
        body = json.dumps(payload, sort_keys=True, indent=2)
        blocks.append(f'<evidence id="{ev.evidence_id}">\n{body}\n</evidence>')
    return "\n\n".join(blocks)


def parse_evidence_fence_ids(prompt: str) -> set[str]:
    """Recover every `<evidence id="...">` id present in a prompt.

    Returns the set of fence id attributes (with `sha256:` prefix preserved).
    Used by the post-generation validator to enforce "cited IDs must appear
    as fences." Not order-preserving — set semantics are sufficient.
    """
    return set(_FENCE_RE.findall(prompt))


class Agent(ABC):
    """Abstract agent.

    Subclasses implement:

      - `name` (class var): stable identifier used in provenance records.
      - `system_prompt_path` (class var): path relative to the agent module
        file pointing at the system prompt markdown.
      - `output_model` (class var): pydantic model the raw LLM JSON is parsed
        into *per invocation*. Not necessarily the same type the agent's
        top-level `run(...)` returns — an agent that loops over many inputs
        (e.g. the Documentation Agent drafting one narrative per KSI) uses
        `output_model` for the per-call LLM shape and aggregates into a
        separate report type.
      - `run(input)`: subclass-defined signature. Assembles user message(s),
        calls `self._invoke_llm(...)` one or more times, and returns a
        typed artifact on the internal model.

    The `_invoke_llm` helper:
      1. Calls the injected `LLMClient`.
      2. Parses the returned text as JSON, raising `AgentError` on malformed output.
      3. Validates the JSON against `output_model`.
      4. If a `ProvenanceStore` is active, writes one `claim`-type record
         capturing the system prompt hash, user messages, model, and output.

    Subclasses are responsible for translating the parsed `output_model`
    into downstream `Claim` records with `derived_from=[...evidence_ids...]`.
    """

    name: str = ""
    system_prompt_path: str = ""
    output_model: type[BaseModel]

    def __init__(
        self,
        *,
        client: LLMClient | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        if not self.name:
            raise AgentError(f"{type(self).__name__}: `name` class var is required")
        if not self.system_prompt_path:
            raise AgentError(f"{type(self).__name__}: `system_prompt_path` class var is required")
        self.client: LLMClient = client or get_default_client()
        self.model = model

    def _load_system_prompt(self) -> str:
        """Resolve `system_prompt_path` against the subclass's module directory."""
        import sys

        module = sys.modules[type(self).__module__]
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            raise AgentError(f"{type(self).__name__}: cannot resolve module file for prompt load")
        prompt_path = Path(module_file).parent / self.system_prompt_path
        if not prompt_path.is_file():
            raise AgentError(f"{type(self).__name__}: system prompt not found at {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    def _invoke_llm(
        self,
        *,
        user_message: str,
        max_tokens: int = 4096,
    ) -> tuple[BaseModel, LLMResponse, str]:
        """Run one completion, parse into `output_model`, emit provenance.

        Returns `(parsed_output, raw_response, system_prompt)` so subclasses
        can re-derive the fenced evidence IDs from the same prompt the model
        saw when building their claim citations.
        """
        system_prompt = self._load_system_prompt()
        response = self.client.complete(
            system=system_prompt,
            messages=[LLMMessage(content=user_message)],
            model=self.model,
            max_tokens=max_tokens,
        )

        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"{self.name}: LLM response was not valid JSON: {e}. "
                f"First 200 chars: {response.text[:200]!r}"
            ) from e

        try:
            output = self.output_model.model_validate(parsed)
        except ValidationError as e:
            raise AgentError(
                f"{self.name}: LLM output failed {self.output_model.__name__}: {e}"
            ) from e

        store = get_active_store()
        if store is not None:
            store.write_record(
                payload={
                    "user_message": user_message,
                    "response_text": response.text,
                    "parsed": parsed,
                },
                record_type="claim",
                agent=self.name,
                model=response.model,
                prompt_hash=response.prompt_hash,
                metadata={"kind": "llm_invocation"},
            )
        else:
            log.warning(
                "agent %s ran with no active provenance store; skipping invocation record",
                self.name,
            )

        return output, response, system_prompt
