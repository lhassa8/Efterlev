# Day 1 brief

The single page you keep open while writing code on Day 1 of the hackathon. You've read `CLAUDE.md`; this is the quick-reference distillation.

## Re-read these in order at session start

Everything below assumes them:

1. [`docs/scope.md`](./scope.md) — v0 MVP contract. Wins on any scope question.
2. [`docs/dual_horizon_plan.md`](./dual_horizon_plan.md) §2.3 — day-by-day plan and exit criteria.
3. [`docs/architecture.md`](./architecture.md) — three-concept system, evidence-vs-claims distinction.
4. [`DECISIONS.md`](../DECISIONS.md) 2026-04-20 entry — the review log that surfaced the five design calls below.

## The five design calls

Resolve each with a dated `DECISIONS.md` entry *before* code lands that locks the choice in.

1. **SC-28 unmapped-control representation.** FRMR 0.9.43-beta lists SC-28 in no KSI's `controls` array. Do not invent a KSI. Pick one of: (a) accept KSI-SVC-VRI with an honest docstring caveat; (b) reframe the detector around integrity (SC-13) rather than at-rest confidentiality (SC-28); (c) represent as `controls_evidenced=["SC-28"]` with `ksis_evidenced=[]` and render as "evidenced at 800-53 level; no current KSI mapping."

2. **Scanner-only FRMR skeleton path.** Some users cannot reach the Anthropic API from their environment. Decide where the deterministic path that produces an evidence-only FRMR skeleton (every narrative field `null`, `mode: "scanner_only"` at top) lives: a deterministic primitive, or a Documentation Agent branch.

3. **Prompt-injection defense shape.** Evidence records will carry free-text strings originally extracted from Terraform (comments, descriptions). Agent prompts treat evidence as data via XML-style fencing (`<evidence id="..."> ... </evidence>`) with the instruction body outside the fence. Confirm this structure in the first prompt draft and lock it.

4. **MCP trust model.** Every primitive is exposed to every connected MCP client. v0 stays stdio-only (no TCP listener). Every tool invocation logs to the provenance store with a client-identifier field. `THREAT_MODEL.md` gets an MCP-attack-surface section.

5. **Provenance receipt log.** Content-addressing catches in-graph tampering but not DB-level attacks. v0 ships a file-based append-only receipt log — one line per new record. Decide the format (`ts|record_id|record_type|parent_ids_hash` is the expected shape) and commit the decision.

## Vertical slice discipline

One detector end-to-end before replicating. The anchor for Day 1:

```
aws.encryption_s3_at_rest
  ↳ detector.py  →  Evidence record
    ↳ store      →  ProvenanceRecord
      ↳ CLI     →  efterlev provenance show <id>  walks back to main.tf:NN
```

Get this working against `demo/govnotes/` before starting the second detector. `docs/dual_horizon_plan.md` §2.3 Day 1 bulleted list is the exit criteria.

## After every commit

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/efterlev && uv run pytest
```

CI runs the same on push. The two pre-hackathon smoke scripts are still useful as sanity pings:

```bash
uv run python scripts/trestle_smoke.py       # NIST 800-53 catalog loads via trestle
uv run python scripts/catalogs_crossref.py   # FRMR ↔ 800-53 cross-reference clean
```

## Permanent guardrails

- **Evidence vs. Claims is a type distinction, not a convention.** `Claim.requires_review: Literal[True] = True` — enforced at the class boundary, not via config.
- **Every Claim cites real evidence.** Per-agent post-generation citation validators (`_validate_cited_ids` in `gap.py`, `documentation.py`, `remediation.py`) reject any Claim citing a sha256 that didn't appear in a legitimately-nonced fence in the prompt. A separate store-write-time `validate_claim_provenance` primitive is a deferred v1.x defense-in-depth item.
- **Never invent a KSI.** If FRMR doesn't list the control under any KSI, mark the mapping as unmapped and surface the gap honestly. See design call #1.
- **Agent prompts are product code.** Surface the full diff in chat for human review before committing, per `CLAUDE.md`.
- **Every non-trivial decision appends to `DECISIONS.md`.** Date, decision, rationale, alternatives considered.
- **Centralize the LLM client** in `src/efterlev/llm/__init__.py` — do not scatter `anthropic.Anthropic()` calls across agent files. Provenance logging happens here at the call boundary; redaction is a planned v1.x addition (not implemented at v0; see `THREAT_MODEL.md` "Secrets handling — current state and planned redaction").

## One finding worth surfacing now

**The FRMR attestation output shape is not publicly defined yet.** `FedRAMP/docs` ships the requirements file (`FRMR.documentation.json`) and the schema (`FedRAMP.schema.json`) that validates it — but no populated example attestations exist in the repo. Phase 2 CSP artifacts (including Aeroplicity's April 13 authorization) are not published. Day 1's Documentation Agent defines the attestation JSON shape from first principles, using our internal `AttestationDraft` Pydantic model as the shape of record. Validate against `FedRAMP.schema.json` where the schema extends to attestations; note explicitly in `LIMITATIONS.md` where schema coverage ends.

## Vendored pins (quick reference)

| Artifact | Source | Pin | SHA-256 |
|---|---|---|---|
| FRMR 0.9.43-beta (2026-04-08) | `FedRAMP/docs` | `a06fa8f9` | `bbb734e9...` |
| NIST 800-53 Rev 5.2.0 | `usnistgov/oscal-content` | `bc8a5287` | `1645df6a...` |
| govnotes demo target | `lhassa8/govnotes-demo` | `0e33252` | (submodule) |

Dep floors after the 2026-04-20 CVE cleanup: `compliance-trestle>=4.0.2`, `cryptography>=46.0.7`, `pytest>=9.0.3`. Full provenance in `catalogs/README.md` and `uv.lock`.
