# CLAUDE.md — Efterlev

This file is your persistent context for working on Efterlev. Read it at the start of every session.

---

## What we're building

**Efterlev** is a repo-native, agent-first compliance scanner for FedRAMP 20x. It runs locally in the developer's codebase and CI pipeline — not in a SaaS dashboard — and produces code-level evidence, FRMR-compatible attestation drafts, and code-level remediation diffs. The internal abstraction is the **Key Security Indicator (KSI)** — the outcome-based unit FedRAMP 20x is built around. Detectors evidence KSIs; KSIs reference 800-53 controls; the user-facing surface speaks KSIs.

The name is a shortening of the Swedish *efterlevnad* (compliance). Pronounce it "EF-ter-lev."

**Primary user (the ICP lens for every product decision):** a SaaS company (50–200 engineers) pursuing its first FedRAMP Moderate authorization, with a committed federal deal on the line. Full ICP at `docs/icp.md` — read it before proposing features, because the ICP is how we decide what Efterlev does and doesn't do.

License: Apache 2.0. No commercial tier, no managed SaaS, no paid layer. Pure OSS, throughout. Competitive positioning lives in `COMPETITIVE_LANDSCAPE.md`.

---

## Current state

**v0.1.2 is current** (shipped 2026-04-30). Public on GitHub at `efterlev/efterlev`, on PyPI as `efterlev`, on `ghcr.io/efterlev/efterlev` (multi-arch, cosign-signed).

The v0.1.x patch arc closed three real-CI bugs surfaced by the deep-dive shakedown against the canonical dogfood target (govnotes-demo): max_tokens truncation in the Gap Agent (v0.1.1 raised the cap); the bumped cap then tripped Anthropic's streaming-required threshold (v0.1.2 reduced to 20480); `__version__` drift between `__init__.py` and `pyproject.toml` (v0.1.1 switched to hatch dynamic versioning); `report run` init-detection looking at the workspace dir instead of the FRMR cache (v0.1.2). See `CHANGELOG.md` for the per-release record.

**Coverage at v0.1.2:**
- 45 detectors total (38 KSI-mapped + 7 supplementary 800-53-only)
- 31 of 60 thematic KSIs covered, across 8 of 11 themes (CNA, CMT, IAM, MLA, PIY, RPL, SCR, SVC)
- 3 agents: Gap (Opus 4.7), Documentation (Sonnet 4.6), Remediation (Opus 4.7)
- Two LLM backends: direct Anthropic (default) + AWS Bedrock (`[bedrock]` extra, GovCloud)
- 1026 tests passing; mypy strict + ruff check + ruff format clean across 172 source files

**Authoritative sources for "what's in":**
- `CHANGELOG.md` — release-by-release record. Don't restate it here.
- `git log` — commit-level history
- `DECISIONS.md` — append-only architectural decision log; every non-trivial choice is here
- `docs/followups.md` — tracker for v0.1.x and v0.2.0+ deferred work

**Canonical dogfood target:** `lhassa8/govnotes-demo`. 24 documented "deliberate gaps" spanning 16 KSIs across 8 themes, plus 3 Evidence Manifests for procedural AFR/CED/INR theme KSIs. Synthetic FedRAMP boundary built specifically for compliance-scanning evaluation. Re-running the full pipeline against it costs ~$2.60 in Anthropic API and is the reference test for any non-trivial Efterlev change. The repo's own `efterlev-scan.yml` workflow runs the full pipeline on every push touching infra/workflows/manifests.

**What's deferred** (not in v0.1.x): OSCAL-shaped SSP/AR/POA&M JSON generators (v1.5+, gated on customer pull); non-Terraform input sources (CloudFormation, CDK, Pulumi, Kubernetes — v1.5+); CMMC 2.0 overlay (v1.5+); runtime cloud API scanning (different threat model — v1.5+); streaming refactor of the Anthropic client (v0.2.0, the right fix for output-budget growth past ~24K tokens).

---

## Known gotchas (v0.1.x lessons)

These have all surfaced in real CI, so they're not theoretical:

- **Anthropic non-streaming threshold.** `client.messages.create()` rejects requests whose `max_tokens` could plausibly take >10 minutes ("Streaming is required for operations that may take longer than 10 minutes"). Empirically, `max_tokens > ~24000` for Opus 4.7 trips this on real workloads. v0.1.2 holds the Gap Agent at 20480 — enough headroom over the v0.1.0 truncation site (~16384 was too small for a full-baseline classification with substantive rationales). Pushing the cap past ~24K means switching to `client.messages.stream()`. Don't bump the cap blindly.

- **`.efterlev/manifests/` committed; everything else gitignored.** This is the canonical Evidence-Manifest pattern. A fresh clone has the workspace dir present (because manifests are checked in) but the FRMR cache, provenance store, etc. missing. `report run` and `init` both check for the FRMR cache file (`.efterlev/cache/frmr_document.json`), not just the dir, to distinguish "fully initialized" from "half-initialized." If you change the init-detection logic, preserve this distinction.

- **`__version__` lives in `src/efterlev/__init__.py` only.** `pyproject.toml` reads it via `[tool.hatch.version] path = "src/efterlev/__init__.py"`. There's a CI-time regression test (`test_in_source_version_matches_package_metadata`) that asserts `efterlev.__version__ == importlib.metadata.version("efterlev")`. Bumping the version means editing `__init__.py` only and rebuilding (uv sync handles this on dev; hatch handles it on the wheel build).

- **`# nosemgrep:` annotations need the full registry-resolved rule_id, not the short name.** Bare `# nosemgrep` (suppress all on the line) works; `# nosemgrep: dangerous-subprocess-use-audit` does NOT, because semgrep matches against `python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit` (the full path from the registry pack). Caused every push-event ci-security run on main to fail silently from v0.1.0 launch through v0.1.1.

- **`python-hcl2` doesn't resolve `${...}` interpolations.** Detectors matching string literals (e.g., `policy_arn == "arn:aws:iam::aws:policy/AdministratorAccess"`) miss when the source uses `arn:${local.partition}:iam::aws:...`. For test targets, hardcode `arn:aws:`. For real-world detection robustness, use plan-JSON mode (`efterlev scan --plan plan.json`) which gives Terraform-resolved values.

- **GitHub-source detectors fire only when the scan target sees `.github/workflows/`.** `efterlev scan --target infra/terraform/` skips them. For mixed-content repos, scan from repo root (`--target .`) — `.tf` files are still found via rglob.

---

## Non-negotiable principles

These override local convenience. If you feel tempted to violate one, stop and ask.

1. **Evidence before claims.** Deterministic scanner output is primary, high-trust, citable. LLM-generated content (narratives, classifications, mappings, remediation proposals) is secondary, carries confidence levels, and is explicitly marked "DRAFT — requires human review" in output. The two classes are visible in the data model, the FRMR output, and every rendered report.
2. **Provenance or it didn't happen.** Every generated claim — finding, narrative, classification, remediation — emits a provenance record linking it to its upstream sources (detector output, evidence records, LLM calls). No exceptions, not for speed, not for demo polish.
3. **FRMR primary, OSCAL secondary.** The user-facing layer is KSIs and Themes; 800-53 Controls remain first-class because KSIs reference them, but they're the underlying layer. FRMR-compatible JSON is what the Documentation Agent produces. OSCAL-shaped output generators are v1.5+ for users transitioning Rev5 submissions. The internal data model is our own Pydantic types; FRMR and OSCAL are produced at the output boundary, not used as internal representations.
4. **Detectors are the moat; primitives are the interface.** The detection library is a community-contributable asset. Each detector is a self-contained folder a contributor can add without touching the rest of the codebase. Primitives are the stable, MCP-exposed surface over which agents reason.
5. **Agent-first, pragmatically.** Every primitive is exposed via the MCP server. External agents (other Claude Code sessions, third-party tools) can discover and call every primitive. Our own agents prefer the MCP interface because it proves the architecture, but direct Python imports are acceptable when they materially improve performance or reliability.
6. **Drafts, not authorizations.** Efterlev never claims to produce an ATO, a pass, or a guarantee of compliance. It produces drafts that accelerate the human/3PAO process. This is not hedging; it's the truth, and it's the only claim that survives serious scrutiny.
7. **Honesty over polish.** If a detector can't prove a KSI, say so in the docstring's "does NOT prove" section. If a feature exists in docs but not in code, fix the docs, not the code (unless the code should exist). Overclaiming is the failure mode 3PAOs reject tools for.

---

## Tech stack

- **Language:** Python 3.12
- **Dependency management:** `uv`
- **Typing:** Pydantic v2 for all primitive I/O. No untyped dicts crossing a primitive boundary.
- **FRMR:** `FRMR.documentation.json` vendored from `FedRAMP/docs` into `catalogs/frmr/`. Single authoritative JSON file (`info`, `FRD`, `FRR`, `KSI`). On load, validated against `FedRAMP.schema.json` (JSON Schema draft 2020-12). On output, attestation artifacts use Pydantic structural validation (`extra="forbid"` + strict literals) — FedRAMP has not published an attestation-output schema, so the catalog schema doesn't apply to our output.
- **OSCAL (input only at v0.1.0):** `compliance-trestle` 4.x for loading the vendored NIST SP 800-53 Rev 5 catalog. OSCAL *output* generation is v1.5+.
- **MCP:** Official Anthropic Python SDK. Stdio transport.
- **LLM backends:** `LLMClient` protocol with `AnthropicClient` (direct API) and `AnthropicBedrockClient` (Converse API). Default model `claude-opus-4-7` for Gap and Remediation; `claude-sonnet-4-6` for Documentation. Centralize client instantiation in `src/efterlev/llm/__init__.py` — do not scatter `anthropic.Anthropic()` calls across agent files.
- **Storage:** SQLite for the provenance index. Content-addressed blob store on disk under `.efterlev/store/` (SHA-256 filenames). Append-only.
- **CLI:** Typer. Single entry point: `efterlev`.
- **IaC parsing:** `python-hcl2` for `.tf` files. `terraform show -json` plan output normalizes through `efterlev.terraform.parse_plan_json` into the same `TerraformResource` shape detectors consume.
- **Testing:** `pytest`. Every primitive and detector has ≥1 happy-path and ≥1 error-path test. No coverage targets — we optimize for confidence, not numbers.
- **Formatting:** `ruff` for lint + format. `mypy --strict` on `src/efterlev/{primitives,detectors,oscal,manifests}.*`.
- **Docs:** MkDocs Material at `efterlev.com`.

---

## Repository layout

```
efterlev/
├── CLAUDE.md                          # this file
├── README.md                          # user-facing
├── CHANGELOG.md                       # release history (Keep a Changelog)
├── CONTRIBUTING.md, CODE_OF_CONDUCT.md, GOVERNANCE.md
├── DECISIONS.md                       # running log of non-trivial choices — APPEND-ONLY
├── LIMITATIONS.md                     # honest scope: what the tool does and doesn't do
├── THREAT_MODEL.md                    # security posture
├── COMPETITIVE_LANDSCAPE.md           # honest positioning
├── SECURITY.md                        # coordinated disclosure
├── LICENSE                            # Apache 2.0
├── docs/
│   ├── architecture.md, faq.md, quickstart.md, deployment-modes.md
│   ├── aws-coexistence.md             # how Efterlev fits next to AWS Config / Security Hub
│   ├── csx-mapping.md                 # how Efterlev's outputs map to CSX-SUM/MAS/ORD
│   ├── ci-integration.md              # GitHub Action setup
│   ├── deploy-govcloud-ec2.md         # GovCloud EC2 + Bedrock walkthrough
│   ├── detector-mapping-audit.md      # KSI-mapping audit trail
│   ├── dual_horizon_plan.md           # roadmap beyond v0.1.0
│   ├── followups.md                   # v0.1.x and v0.2.0+ deferred work
│   ├── icp.md                         # Ideal Customer Profile
│   ├── manual-verification-runbook.md
│   ├── RELEASE.md                     # release process + verify-release.sh contract
│   ├── security-review-2026-04.md     # pre-launch security review (signed)
│   ├── concepts/, tutorials/, comparisons/, reference/   # public docs site
│   └── specs/                          # internal SPEC documents
├── src/efterlev/
│   ├── models/                        # Pydantic types (Indicator, Control, Evidence, Claim, ...)
│   ├── frmr/                          # FRMR loader + validator + generator
│   ├── oscal/                          # 800-53 catalog loader; OSCAL output generator (v1.5+)
│   ├── detectors/
│   │   ├── aws/<capability>/          # one folder per detector
│   │   └── github/<capability>/       # github-workflows detectors
│   ├── primitives/{scan,map,evidence,generate,validate}/
│   ├── manifests/                     # Evidence Manifest loader + types
│   ├── terraform/                     # HCL + plan-JSON parsing
│   ├── github_workflows/              # workflow YAML parsing
│   ├── llm/                           # LLMClient protocol + scrubber + retry/fallback
│   ├── mcp_server/
│   ├── agents/                        # gap.py + gap_prompt.md, etc.
│   ├── provenance/                    # store + walker
│   ├── reports/                       # HTML renderers
│   └── cli/
├── catalogs/{frmr,nist}/              # vendored reference data
├── demo/govnotes/                     # sample target app
├── scripts/                           # e2e_smoke.py, ci_pr_summary.py, verify-release.sh, ...
└── tests/
```

When adding new detectors, match the source/capability folder. When adding primitives, match the capability verb (`scan`, `map`, `evidence`, `generate`, `validate`). If it doesn't fit, propose a new subfolder before creating it.

---

## The detector contract

A detector is a self-contained artifact. One folder per detector. A contributor can add a new detector without reading the rest of the codebase. This is the #1 design commitment for long-term project health.

Each detector folder contains:

- **`detector.py`** — pure function, typed input/output. Reads source material (Terraform resources, GitHub workflow YAML), emits `Evidence` records.
- **`mapping.yaml`** — which KSI(s) this detector evidences, plus the underlying 800-53 control(s). Multi-target mappings are fine.
- **`evidence.yaml`** — template describing the shape and semantics of evidence this detector produces. Internal schema, not FRMR or OSCAL.
- **`fixtures/`** — `should_match/` and `should_not_match/` samples the test harness runs against.
- **`README.md`** — what this detector checks, what it proves, what it does NOT prove, known limitations. The "does NOT prove" section is required.

Detector IDs are capability-shaped (what the detector checks), not control-shaped. KSIs think in capabilities; IDs like `encryption_s3_at_rest` age better than `sc_28_s3_encryption` as the KSI ↔ control mapping evolves.

**Two mapping disciplines applied across the catalog:**

1. **`ksis=[]` is honest when no KSI maps the control.** SC-28 (encryption at rest) is the largest example: 5 of the 7 supplementary 800-53-only detectors carry `ksis=[]` because FRMR 0.9.43-beta does not list SC-28 in any KSI's `controls` array. Their evidence surfaces in the gap report's "Unmapped findings" section. Tracked as an upstream FRMR issue, not an Efterlev mapping mistake.
2. **Control membership in a KSI's `controls` array is necessary but not sufficient for claiming the KSI.** The detector must also evidence what the KSI's *statement* commits to. Example: IA-5 appears in KSI-IAM-MFA's controls, but `aws.iam_password_policy` does NOT claim KSI-IAM-MFA — password policy doesn't evidence phishing-resistant MFA.

See `docs/detector-mapping-audit.md` for the full per-detector audit.

---

## The primitive contract

Primitives are the MCP-exposed agent interface. Small and stable.

**Two classes of primitives, different contracts:**

**Deterministic primitives** — scan, map, validate, parse, hash, serialize. Pure where possible. Side-effecting primitives (write files, open PRs) are flagged.

```python
@primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
def scan_terraform(input: ScanTerraformInput) -> ScanTerraformOutput:
    """Run all applicable detectors against a Terraform source tree."""
```

**Generative primitives** — narrative synthesis, classification, remediation. LLM-backed. Output carries confidence levels and a `requires_review: Literal[True]` flag.

**Shared rules:**
- Verb-noun snake_case name
- One Pydantic input model, one Pydantic output model
- Docstring states intent, side effects, deterministic/generative, external dependencies
- Emits a provenance record via decorator machinery — you do not write provenance code inside the function body
- Auto-registered with the MCP server by the decorator
- No `print`; use the standard logger
- Raises typed exceptions from `efterlev.errors`, never bare `Exception`

---

## The agent contract

Every agent:

- Subclasses `efterlev.agents.base.Agent`
- Has its system prompt in a sibling `.md` file (`gap.py` → `gap_prompt.md`). **Prompts are product code — do not inline them as Python strings.**
- Consumes primitives via the MCP tool interface by default. Direct imports from `efterlev.primitives.*` are allowed when MCP round-tripping adds no value; flag the choice in the agent's docstring.
- Produces a typed output artifact on our internal model (e.g. `GapReport`, `AttestationDraft`, `RemediationProposal`). FRMR and OSCAL serialization are separate generator steps, not the agent's job.
- Logs every tool call, model response, and final artifact to the provenance store
- Is invokable standalone from the CLI: `efterlev agent <name> [options]`

**When you write or revise an agent's system prompt, surface the full diff in chat for review before committing.** Agent prompts are the product's brain; they deserve human sign-off even when code doesn't.

**Hallucination defenses are structural, not advisory:**
- Every agent prompt wraps evidence in `<evidence_NONCE id="sha256:...">...</evidence_NONCE>` XML fences, with a per-run nonce (`secrets.token_hex(4)`) that prevents content-injected forged fences.
- A post-generation validator rejects any output that cites evidence IDs not present as fences in the prompt the model actually saw.
- `ProvenanceStore.write_record` validates every Claim's `derived_from` at write time — unresolvable IDs raise `ProvenanceError` before insertion.
- Every Claim carries `requires_review: Literal[True]` at the type level — not a string, not a flag.

**Secret redaction is unconditional:** every LLM prompt is scrubbed for 7 secret families (AWS, GCP, GitHub, Slack, Stripe, PEM, JWT) before egress. The scrubber lives in `src/efterlev/llm/scrubber.py`; it's called by `format_evidence_for_prompt` and `format_source_files_for_prompt` in `agents/base.py` with no opt-out path. Each redaction writes to `.efterlev/redactions/<scan_id>.jsonl` (mode `0o600`); `efterlev redaction review` renders the log.

**LLM calls degrade predictably:** transient Anthropic errors retry with exponential backoff + full jitter (3 attempts on primary). Primary-model exhaustion falls back once to a configured secondary (Opus 4.7 → Sonnet 4.6 by default) before surfacing.

---

## Evidence vs. claims: the data model

Two distinct types, treated differently throughout the system. See `src/efterlev/models/evidence.py` and `claim.py` for the canonical definitions.

- **`Evidence`** — deterministic, scanner-derived, content-addressed by SHA-256. Fields: `evidence_id`, `detector_id`, `ksis_evidenced`, `controls_evidenced`, `source_ref` (file + line + commit), `content`, `timestamp`.
- **`Claim`** — LLM-reasoned, content-addressed. Fields: `claim_id`, `claim_type` (narrative / classification / remediation / mapping), `content`, `confidence`, `requires_review: Literal[True]`, `derived_from`, `model`, `prompt_hash`, `timestamp`.

Every rendered output — HTML report, FRMR artifact, terminal summary — visually distinguishes Evidence (green left border) from Claims (amber, with the DRAFT banner). Manifest-sourced citations carry an additional "attestation" pill to distinguish human-signed from scanner-derived evidence.

---

## Provenance model

Every claim is a node in a directed graph. Edges point from derived claims to upstream sources.

```python
class ProvenanceRecord(BaseModel):
    record_id: str                      # sha256 of canonical content
    record_type: Literal["evidence", "claim", "finding", "mapping", "remediation"]
    content_ref: str                    # path in blob store
    derived_from: list[str]             # upstream record_ids (evidence or claim)
    primitive: str | None               # "scan_terraform@0.1.0"
    agent: str | None                   # "gap_agent" if agent-mediated
    model: str | None                   # "claude-opus-4-7" if LLM-involved
    prompt_hash: str | None             # hash of system prompt if LLM-involved
    timestamp: datetime
    metadata: dict
```

Rules:
- A record with `derived_from=[]` is raw evidence or a primitive input. Any reasoning step must carry its inputs forward.
- Records are immutable and append-only. New evidence for a KSI creates a new record; it does not overwrite the old one.
- `efterlev provenance show <record_id>` walks the chain to source-file line ranges.

When you implement a primitive or agent that generates records, **write the provenance walk test first**. If the chain doesn't resolve end-to-end, the feature isn't done.

---

## Quality bar

- **Every detector:** typed I/O, docstring with "proves / does NOT prove," fixtures for should-match and should-not-match, passing tests, plan-JSON equivalence test.
- **Every primitive:** typed I/O, docstring, ≥1 happy test, ≥1 error test, FRMR validation on output where applicable, provenance record emitted.
- **Every agent:** system prompt in its own file, provenance-emitting, CLI-invokable, end-to-end test against the demo repo.
- **Every commit:** `ruff check` clean, `ruff format --check` clean, `mypy --strict` clean on core paths, tests passing.
- **Every non-trivial decision:** appended to `DECISIONS.md` with date, decision, rationale, alternatives considered.

---

## How we work together

- **Surface architectural questions immediately.** If you see a fork in the road, stop and ask. Do not silently pick and refactor later.
- **Prefer small PRs.** If a change touches more than three files outside of pure additions, flag it.
- **GitHub Actions minutes are constrained** (~90% of monthly cap as of 2026-04-28). Batch related changes into one PR; run gates locally before pushing; avoid fixup-push churn.
- **Maintain `DECISIONS.md`.** Every non-obvious choice belongs there. Append-only — historical entries stay even when the decision is later reversed; add the reversal as a new dated entry.
- **Prompts are product.** Surface system-prompt diffs in chat before committing.

---

## Never do

- Never commit real secrets, API keys, or production data. The demo repo is synthetic.
- Never return FRMR (or, in v1.5+, OSCAL) output that hasn't passed Pydantic structural validation.
- Never generate a Claim without citing the Evidence records it derives from.
- Never claim the tool produces an ATO, a pass, or a guarantee of compliance. Drafts and findings only.
- Never add a dependency without a line in `DECISIONS.md` explaining why.
- Never mix Evidence and Claims in a way that loses their distinction — in the data model, in the UI, or in FRMR/OSCAL output.
- Never claim a detector proves more than it actually does. The "does NOT prove" section of the detector README is as important as the "does prove" section.
- Never invent a KSI ID that does not appear in the vendored FRMR. If coverage is genuinely missing, surface the gap and file an upstream issue; do not paper over it.
- Never bypass the secret scrubber or the fence-citation validator. Both are unconditional by design.

---

## References

- `CHANGELOG.md` — release-by-release record
- `DECISIONS.md` — append-only architectural decision log
- `LIMITATIONS.md` — honest scope of what the tool does and doesn't do
- `THREAT_MODEL.md` — security posture for the tool itself
- `COMPETITIVE_LANDSCAPE.md` — positioning against Comp AI, Vanta/Drata, RegScale OSCAL Hub, and others
- `docs/architecture.md` — deeper architectural detail
- `docs/icp.md` — the Ideal Customer Profile; lens for every product decision
- `docs/dual_horizon_plan.md` — roadmap beyond v0.1.0
- `docs/followups.md` — v0.1.x and v0.2.0+ deferred work

When any of those conflict with this file on a current-state question, this file wins and we update the others. Where this file conflicts with the actual code, the code wins and we update this file.
