# Customize an agent prompt

Stub for SPEC-38.11. Substantial content lands in a follow-up batch.

Each agent's system prompt lives in a sibling `.md` file beside its agent code: `src/efterlev/agents/gap_prompt.md`, `documentation_prompt.md`, `remediation_prompt.md`. Customizing means editing the prompt and re-running.

What discipline is non-negotiable across any prompt customization:

- **Per-run fence-nonce rules.** Every prompt wraps cited evidence in `<evidence_NONCE id="sha256:...">...</evidence_NONCE>` fences with a per-run nonce. The post-generation validator rejects output that cites IDs not present as fences. Removing this is removing the hallucination defense.
- **DRAFT marker.** Every Claim carries a `requires_review=Literal[True]` invariant. The prompt must instruct the LLM to produce output that lands inside this invariant; you can't relax to `Literal[False]` via prompt engineering — the type system catches it.
- **Citation discipline.** Agents cite by content-addressed ID, not by paraphrase. The Gap Agent's prompt instructs the model to cite specific evidence records when classifying; weakening this regresses provenance integrity.

After editing, run the e2e harness:

```bash
ANTHROPIC_API_KEY=... uv run python scripts/e2e_smoke.py
```

If checks fail, the prompt change broke something. Read `.e2e-results/<ts>/summary.md` for the specific failure.
