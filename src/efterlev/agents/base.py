"""Shared agent scaffolding: evidence fencing, prompt loading, base class.

Four things live here:

  1. `new_fence_nonce()` — generates a per-run random hex nonce. Agents
     create one nonce at the top of a `run()` call and pass it to every
     fence format/parse operation in that call. The nonce is what
     prevents adversarial content from forging closing tags to break
     out of a fence (DECISIONS 2026-04-22 Phase 2 post-review fixup F,
     hardening design call #3 from 2026-04-21).

  2. `format_evidence_for_prompt(evidence, nonce=…)` — the *only* way
     agents should embed Evidence content into a prompt. Each record is
     wrapped in an `<evidence_NONCE id="sha256:...">...</evidence_NONCE>`
     fence. `format_source_files_for_prompt(source_files, nonce=…)` is
     the analogous helper for raw `.tf` file content — same nonce, same
     trust model, different fence tag name so the validator can enforce
     citation rules separately per class.

  3. `parse_evidence_fence_ids(prompt, nonce=…)` /
     `parse_source_file_fence_paths(prompt, nonce=…)` — recover the set
     of fence IDs/paths actually present in a prompt with the caller's
     nonce. Used by post-generation validators to confirm every cited
     ID or path maps to a real fence; content-injected fences with any
     other nonce are ignored.

  4. `Agent` — abstract base. Subclasses declare `name`, `system_prompt_path`,
     and an `output_model` pydantic class; `Agent._invoke_llm(...)` loads the
     prompt, calls the LLM via the injected client, parses + validates the
     response, and emits a provenance record for the model invocation.
     Subclasses build the user message(s) and transform the parsed JSON
     into the final typed artifact.

Fencing is mandatory for anything scanner-derived or attacker-controllable.
Any agent that assembles its own evidence or source-file strings bypasses
the prompt-injection defense the whole generative layer depends on.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
from abc import ABC
from pathlib import Path

from pydantic import BaseModel, ValidationError

from efterlev.errors import AgentError
from efterlev.llm import DEFAULT_MODEL, LLMClient, LLMMessage, LLMResponse, get_default_client
from efterlev.llm.scrubber import RedactionLedger, scrub_llm_prompt
from efterlev.models import Evidence
from efterlev.provenance.context import get_active_store

log = logging.getLogger(__name__)


def new_fence_nonce() -> str:
    """Return a fresh random nonce for a single agent run's fence set.

    The nonce is a 32-bit hex string generated via `secrets.token_hex(4)` —
    cryptographically random, unpredictable at evidence-authoring time,
    cheap to embed in tag names. Eight hex chars is enough entropy that an
    adversarial content author cannot guess the nonce and embed a matching
    closing tag to break out of the fence.

    Callers generate ONE nonce at the top of an agent run and pass it to
    every `format_*_for_prompt` / `parse_*_fence_*` call in that run. All
    legitimate fences in a single prompt share the same nonce; content
    cannot forge fences because it does not know the nonce.
    """
    return secrets.token_hex(4)


def format_evidence_for_prompt(
    evidence: list[Evidence],
    *,
    nonce: str,
    redaction_ledger: RedactionLedger | None = None,
) -> str:
    """Return a prompt fragment wrapping each Evidence in a nonced XML fence.

    Fence format: `<evidence_NONCE id="<evidence_id>">` + JSON-serialized
    content + `</evidence_NONCE>`. The `evidence_id` already carries the
    `sha256:` prefix (see `models._hashing.compute_content_id`), so the
    rendered fence id matches the provenance record_id format exactly.

    Why the nonce: without it, an adversarial input whose content contains
    `</evidence>` could break out of its fenced region and inject fake
    fences. With a fresh random nonce per call, content-authored strings
    cannot forge a matching closing tag or an alternative opening tag for
    a fabricated evidence id — the attacker would have to predict 32 bits
    of entropy at authoring time.

    Callers get the nonce from `new_fence_nonce()` and pass it to both this
    function and the matching `parse_evidence_fence_ids(nonce=...)` call
    that validates the model's output. Records are emitted in input order.

    Secret redaction (2026-04-23): the rendered per-evidence JSON body is
    scrubbed via `scrub_llm_prompt` before being wrapped in its fence. A
    pattern library in `efterlev.llm.scrubber` catches high-confidence
    structural secrets (AWS keys, GitHub tokens, PEM private keys, etc.)
    and replaces them with `[REDACTED:<kind>:sha256:<8hex>]` tokens. If
    a `redaction_ledger` is supplied, every redaction is logged against
    it with `context_hint="evidence[<detector_id>]:<index>"` for later
    audit via `.efterlev/redacted.log`. Scrubbing is unconditional;
    the ledger is an optional audit sink. Fail-closed: scrubber errors
    propagate and prevent prompt transmission.
    """
    if not evidence:
        return "(no evidence records)"

    blocks: list[str] = []
    for index, ev in enumerate(evidence):
        payload = {
            "detector_id": ev.detector_id,
            "ksis_evidenced": ev.ksis_evidenced,
            "controls_evidenced": ev.controls_evidenced,
            "source_ref": ev.source_ref.model_dump(mode="json"),
            "content": ev.content,
        }
        body = json.dumps(payload, sort_keys=True, indent=2)
        scrubbed_body, events = scrub_llm_prompt(
            body, context_hint=f"evidence[{ev.detector_id}]:{index}"
        )
        if redaction_ledger is not None and events:
            redaction_ledger.extend(events)
        blocks.append(
            f'<evidence_{nonce} id="{ev.evidence_id}">\n{scrubbed_body}\n</evidence_{nonce}>'
        )
    return "\n\n".join(blocks)


def parse_evidence_fence_ids(prompt: str, *, nonce: str) -> set[str]:
    """Recover every `<evidence_NONCE id="...">` id present in a prompt.

    Only matches fences whose nonce equals the caller-provided one — so
    content-injected fences with random or attacker-chosen nonces are
    ignored. Returns the set of fence id attributes (with `sha256:` prefix
    preserved). Used by the post-generation validator to enforce "cited
    IDs must appear as legitimately-fenced records."
    """
    pattern = re.compile(rf'<evidence_{re.escape(nonce)} id="([^"]+)">')
    return set(pattern.findall(prompt))


def format_source_files_for_prompt(
    source_files: dict[str, str],
    *,
    nonce: str,
    redaction_ledger: RedactionLedger | None = None,
) -> str:
    """Return a prompt fragment wrapping each `.tf` file in a nonced XML fence.

    Fence format: `<source_file_NONCE path="<path>">` + raw Terraform +
    `</source_file_NONCE>`. The Remediation Agent needs the full source text
    to produce a valid unified diff, but `.tf` comments are attacker-
    controllable just like Evidence content — a hostile module comment
    could literally contain `</source_file>` to break out of the fence.
    The nonce makes that impossible: the attacker would have to predict
    32 bits of entropy at the time they wrote the comment.

    The content is embedded verbatim (no JSON escaping): the model reads
    it as Terraform, not as a JSON payload.

    Secret redaction (2026-04-23): source file content is scrubbed via
    `scrub_llm_prompt` before being wrapped. Terraform files can legitimately
    carry heredoc-wrapped IAM policies, KMS key material for module tests,
    etc. that match structural secret patterns. The redaction ledger records
    each match with `context_hint="source_file[<path>]"`.
    """
    if not source_files:
        return "(no source files)"

    blocks: list[str] = []
    for path, content in source_files.items():
        scrubbed_content, events = scrub_llm_prompt(
            content, context_hint=f"source_file[{path}]"
        )
        if redaction_ledger is not None and events:
            redaction_ledger.extend(events)
        blocks.append(
            f'<source_file_{nonce} path="{path}">\n{scrubbed_content}\n</source_file_{nonce}>'
        )
    return "\n\n".join(blocks)


def parse_source_file_fence_paths(prompt: str, *, nonce: str) -> set[str]:
    """Recover every `<source_file_NONCE path="...">` path present in a prompt.

    Same nonce-gated discipline as `parse_evidence_fence_ids`. Returns
    only paths from fences opened with the expected nonce.
    """
    pattern = re.compile(rf'<source_file_{re.escape(nonce)} path="([^"]+)">')
    return set(pattern.findall(prompt))


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
    # Per-agent default model. Subclasses override when their workload doesn't
    # need the full Opus reasoning budget — Documentation Agent uses Sonnet
    # because its job is structured extractive writing with tight format
    # compliance, not novel reasoning. Fallback is the package-wide
    # DEFAULT_MODEL so agents that don't override pick up future changes to
    # the global default.
    default_model: str | None = None

    def __init__(
        self,
        *,
        client: LLMClient | None = None,
        model: str | None = None,
    ) -> None:
        if not self.name:
            raise AgentError(f"{type(self).__name__}: `name` class var is required")
        if not self.system_prompt_path:
            raise AgentError(f"{type(self).__name__}: `system_prompt_path` class var is required")
        self.client: LLMClient = client or get_default_client()
        # Resolution order: explicit model arg > subclass default_model >
        # package DEFAULT_MODEL. A caller who explicitly passes a model
        # always wins; subclasses set the sensible default for their task.
        self.model = model or self.default_model or DEFAULT_MODEL

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
