# Decisions Log

Append-only log of non-trivial decisions made during the design and build of Efterlev. This is judge-facing and contributor-facing — it is how people who show up later understand why things are the way they are.

**Format:** Each entry has a date, a decision, the rationale, alternatives considered, and (where applicable) tags. Entries are never deleted; if a decision is reversed, a new entry describes the reversal.

**Tags in use:** `[architecture]`, `[scope]`, `[tool-choice]`, `[positioning]`, `[threat-model]`, `[process]`.

---

## 2026-04-18 — Project name is Efterlev `[positioning]`

**Decision:** Adopt "Efterlev" as the project name.

**Rationale:**
- Shortening of Swedish *efterlevnad* (compliance); domain-resonant but not on-the-nose
- Distinctive in a crowded space where "Comply/Comp"-prefixed names are saturated (Comp AI, ComplyKit, Complyant, etc.)
- Pronounceable on sight ("EF-ter-lev") for English speakers
- Sonic echo of "ever-live / enduring" in English fits continuous compliance
- Expected to be clear of GitHub/PyPI/npm collisions (verify before creating org)

**Alternatives considered:**
- Aegis — overused in security space
- OpenControlAI — collides with Comp AI and the historical 18F OpenControl project
- Complyant, Complir, Proveon, Warrant, Evidentiary — all viable but either crowded or less distinctive
- Junshu (Japanese) — more striking but higher friction for English-speaking users

---

## 2026-04-18 — OSCAL as output, not internal model `[architecture]`

**Decision:** The internal data model is our own Pydantic types (Control, Evidence, Claim, Finding, Mapping, Provenance). OSCAL is produced at the output boundary by dedicated generator primitives. Trestle is used only for loading OSCAL inputs and for validation.

**Rationale:**
- OSCAL adoption at 3PAOs is still thin as of April 2026 (RFC-0024 proposed a September 2026 machine-readable floor; NOTICE-0009 on 2026-03-25 softened the date and moved formalization into the pending Consolidated Rules for 2026, due end of June); users consume Word templates today and OSCAL tomorrow, and we want to serve both
- OSCAL's SSP model is complex and opinionated in ways that don't help our core job (detection, evidence, narrative drafting)
- Users don't ask for OSCAL; they ask for findings and drafts. OSCAL matters at the output boundary, not in the working representation
- An owned internal model is simpler to iterate, test, and extend
- Multiple output formats (OSCAL, FedRAMP Word, HTML, Markdown) are easier to support when the internal model is ours

**Alternatives considered:**
- OSCAL-native internal model (the original plan): rejected because it front-loads OSCAL engineering overhead that doesn't improve detection quality
- No OSCAL at all: rejected because OSCAL output is genuinely valuable for downstream consumers (OSCAL Hub, government systems) and is a real differentiator

---

## 2026-04-18 — Detectors are a first-class concept, separate from primitives `[architecture]`

**Decision:** Detection rules live in a self-contained library at `src/efterlev/detectors/`. Each detector is a folder containing `detector.py`, `mapping.yaml`, `evidence.yaml`, `fixtures/`, and `README.md`. Detectors are community-contributable; a contributor can add a detector without touching the rest of the codebase.

**Rationale:**
- Detector count will grow from six (hackathon) to 80+ (v1) to hundreds (v2+). The extension mechanism is load-bearing for long-term project health.
- Each detector's `README.md` carrying a "proves / does not prove" section is how we enforce the evidence-vs-claims discipline at the source.
- Primitives stay small, stable, and testable (~15–25 at v1). Detectors grow indefinitely through community contribution.
- Python entry points allow external packages (`efterlev_detector_*`) to register themselves, so the core package has no central registry to maintain.

**Alternatives considered:**
- Detectors as a subfolder of primitives: rejected because it conflates a growing community-contributable library with a stable core interface
- Detectors as external plugins only: rejected because the hackathon needs in-repo detectors for the demo; external-only would push all contribution to later

---

## 2026-04-18 — Evidence vs. Claims is a first-class distinction `[architecture]`

**Decision:** The data model has two distinct types with different contracts:
- `Evidence` — deterministic, scanner-derived, high-trust, cites raw source
- `Claim` — LLM-reasoned, carries confidence level, marked "DRAFT — requires human review"

Rendered output (HTML, OSCAL, CLI) always visually distinguishes them.

**Rationale:**
- A 3PAO or compliance reviewer asking "how does this tool defend against hallucination?" needs a structural answer, not a disclaimer
- The distinction matters for auditability: scanner output is verifiable; LLM output is a draft
- Every other AI-compliance tool conflates these, which is one of the things that makes them easy to dismiss

**Alternatives considered:**
- Unified record type with a `generated_by` field: rejected because it makes the distinction easy to lose in rendering and in downstream consumers
- Only deterministic output (no LLM): rejected because narrative generation is a real user value

---

## 2026-04-18 — Six controls in the hackathon MVP, not seventeen `[scope]`

**Decision:** The hackathon MVP detects six controls: SC-28, SC-8, SC-13, IA-2, AU-2+AU-12, CP-9. All others deferred to v1+.

**Rationale:**
- These six have genuinely dispositive infrastructure-layer evidence — a detector can honestly emit evidence without overclaiming
- A 4-day solo build produces six working end-to-end controls better than seventeen half-working ones
- Judges evaluate architectural depth over surface breadth; one control shown fully (scan → evidence → narrative → remediation → provenance walk) is more compelling than seventeen shallow findings
- Controls like AC-2, AU-3, CM-2 require procedural evidence the tool cannot produce from IaC alone. Including them at v0 would force either hedged findings (useless) or overclaimed findings (dishonest)

**Alternatives considered:**
- The original seventeen-control scope: rejected after Round 1 evaluation flagged scope realism as the #1 risk
- Three controls (even narrower): considered, but six gives enough breadth to demonstrate the pattern while remaining buildable

---

## 2026-04-18 — Pragmatic MCP usage, not religious `[architecture]`

**Decision:** Every primitive is exposed via our MCP server. External agents can discover and call every primitive. Our own agents prefer the MCP interface but are allowed direct Python imports where MCP round-tripping adds no value.

**Rationale:**
- The architectural commitment that matters is that external Claude Code can discover and call every primitive (this is the judge-facing proof point and the extension model for the community)
- Internal agents paying MCP round-trip cost for deterministic data transforms adds complexity and latency with zero demo value
- "The useful, demoable solution is what matters" — per the user's explicit guidance

**Alternatives considered:**
- Strict MCP-only for internal agents: rejected as ideological rather than useful
- No MCP at all: rejected because external agent discoverability is the differentiator

---

## 2026-04-18 — Dev-tool positioning, not compliance-platform positioning `[positioning]`

**Decision:** Efterlev is positioned as a repo-native developer tool, not as a compliance platform. The primary user is a DevSecOps engineer; the primary locus is the codebase and CI pipeline; the extension model is a Python package.

**Rationale:**
- Comp AI occupies the OSS AI compliance platform space with real traction (600+ customers)
- RegScale OSCAL Hub occupies the OSS OSCAL platform tier
- The dev-tool-shaped lane — running in the repo, scanning IaC source, producing code-level remediation — is open
- This positioning naturally matches where Claude Code specifically shines (repo execution, code editing, MCP integration)
- It also matches the adoption wedge: `pipx install efterlev` has no procurement cycle

**Alternatives considered:**
- Compete directly with Comp AI on multi-framework OSS compliance: rejected because they're further along and have broader framework coverage
- Compete at the OSCAL-platform tier: rejected because OSCAL Hub owns that space and because the platform tier isn't where our advantage lies

---

## 2026-04-18 — FedRAMP Moderate first, CMMC 2.0 as v1 second framework `[scope]`

**Decision:** Hackathon targets FedRAMP Moderate. v1's second framework is CMMC 2.0 (same 800-171 base, different overlay). StateRAMP is derivative of FedRAMP and comes nearly for free; it is not counted as a separate framework.

**Rationale:**
- CMMC 2.0 represents ~300K DoD contractors with real, current compliance pain
- Same underlying control catalog (800-171 derives from 800-53) means low marginal engineering cost after FedRAMP
- DoD IL4/5/6 are where Comp AI does not play and where government-contractor pain is highest
- SOC 2 / ISO 27001 / HIPAA / PCI-DSS / GDPR are explicitly out of scope — other tools serve those well

**Alternatives considered:**
- SOC 2 as the second framework: rejected because Comp AI and others already serve it well
- ISO 27001: rejected on the same grounds
- HIPAA: different regulatory lineage, not aligned with our FedRAMP/IL focus

---

## 2026-04-18 — Apache 2.0 license `[tool-choice]`

**Decision:** License is Apache 2.0.

**Rationale:**
- Government-adjacent OSS convention is Apache 2.0 or MIT; Apache 2.0 is the more conservative choice for patent-grant clarity
- Compatible with most enterprise procurement policies
- Matches the license of key dependencies (compliance-trestle, Anthropic SDKs)
- Explicit patent grant is useful given this space's interaction with gov procurement and potential patent pools

**Alternatives considered:**
- MIT: acceptable but weaker on patent protection
- AGPL: rejected because it would limit SaaS adoption and we want the tool used broadly

---

## 2026-04-18 — Python 3.12, uv, Pydantic v2, Typer, MkDocs Material `[tool-choice]`

**Decision:** The stack above for the core repo.

**Rationale:**
- Python 3.12: current stable; compliance-trestle is Python-native; IaC parsing ecosystem is strong in Python
- uv: significantly faster than pip; hackathon fit
- Pydantic v2: the typed-I/O layer for all primitive contracts
- Typer: clean CLI ergonomics with minimal boilerplate
- MkDocs Material: docs-as-product from day one; the most widely-used OSS docs framework

**Alternatives considered:**
- Go or Rust: rejected because the OSCAL + compliance ecosystem is Python
- Click instead of Typer: both are fine; Typer chosen for the type-driven ergonomics
- Sphinx for docs: rejected as heavier than needed for this project's docs style

---

## 2026-04-18 — Claude Opus 4.7 as default agent model `[tool-choice]`

**Decision:** Default agent inference model is `claude-opus-4-7`. Fallback to `claude-sonnet-4-6` only if latency becomes a demo-day issue.

**Rationale:**
- Demo quality matters more than inference cost in a 4-day hackathon
- Narrative generation and remediation proposal benefit from stronger reasoning
- Pluggable backend in the agent base class allows swapping later (local models for air-gapped use in v1+)

**Alternatives considered:**
- Sonnet 4.6 as default: rejected for demo; acceptable for v1 if latency pressure emerges
- Multi-model routing (cheap for classification, expensive for narrative): deferred to v1; not worth the complexity for the hackathon

---

## 2026-04-18 — Local-first, no telemetry, no phone-home `[threat-model]`

**Decision:** Efterlev runs locally with no telemetry, no analytics, no phone-home. The only outbound network calls are to the configured LLM endpoint and (on explicit user action) to OSCAL catalog URLs for updates.

**Rationale:**
- Compliance tooling that transmits scanned content is hard to trust
- Air-gap viability is a real user need (DoD, IL5+)
- Adoption wedge for gov-adjacent engineers: `pipx install` with no SaaS procurement cycle
- Simplicity — no telemetry infrastructure to build, secure, and maintain

**Alternatives considered:**
- Opt-in anonymous telemetry: rejected for simplicity and trust posture; v2 may reconsider
- SaaS-hosted mode: rejected at v0; v2 may offer it as an optional deployment model

---

## 2026-04-18 — Bedrock as v1 second backend; v0 is Anthropic-direct only `[architecture]` `[scope]`

**Decision:** The hackathon MVP wires to the Anthropic Python SDK directly. AWS Bedrock is committed as the v1 second backend behind an `LLMClient` abstraction. v0 code must centralize client instantiation in a single module (`src/efterlev/llm/__init__.py`) so the v1 refactor to pluggable backends is a mechanical change to one file.

**Rationale:**
- Efterlev's target user (DevSecOps engineer at a gov-contracting SaaS or defense-industrial-base company) often runs exclusively in AWS GovCloud, where Anthropic direct API is not FedRAMP-authorized but Bedrock has FedRAMP High authorization. A compliance tool that can't run in FedRAMP-authorized environments is self-defeating for this audience.
- Bedrock parity with Anthropic direct is essentially current as of April 2026 — flagship models are available near-simultaneously — so "use Bedrock" is a real option, not a degraded fallback.
- Building the abstraction during a 4-day solo sprint costs a half-day (credential handling, model-ID translation, boto3 SDK wiring, config ergonomics) with zero demo value. The judges are not watching a backend switch.
- The cheap structural hedge — single `get_client()` module — costs nothing at v0 and makes the v1 refactor trivial. This is the right kind of premature factoring: just enough to preserve optionality.

**Alternatives considered:**
- **Build Bedrock support during the hackathon:** rejected. Trades a half-day of real demo-critical work against a capability no judge will see.
- **Anthropic-only forever:** rejected. Forecloses the gov-adjacent buyer entirely, which undermines the project's core positioning.
- **Vertex AI (Claude on GCP) as the second backend instead of Bedrock:** deferred. GCP presence in gov-contractor environments is real but smaller than AWS; Bedrock is the higher-leverage second backend. Vertex follows in v1+.
- **Local models (Ollama, llama.cpp) as the second backend:** deferred. Relevant for air-gapped IL5+ environments but narrative-generation quality lags Claude meaningfully; would produce materially worse drafts. v1+ behind a config flag with explicit quality warnings.
- **OpenAI/Gemini/other model families:** not planned. Dilutes the Claude-native architectural story without serving a committed user segment. Contributors who want these can fork and maintain.

---

## 2026-04-18 — Primary ICP is first-FedRAMP SaaS companies `[positioning]` `[scope]`

**Decision:** The primary user Efterlev is designed for, at v0 and v1, is a SaaS company (50–200 engineers) pursuing its first FedRAMP Moderate authorization. Secondary ICPs are defense contractors pursuing CMMC 2.0 / DoD IL (v1.5+) and large gov-contractor platform teams (v2+). Full ICP document lives at `docs/icp.md` and is the lens for every product decision.

**Rationale:**
- Pain is acute, visible, and budgeted. A SaaS company with a committed federal deal tied to FedRAMP authorization is actively searching for tools, has decision-maker attention, and has a deadline.
- The existing demo flow (`efterlev scan` → gap report → SSP draft → remediation diff) maps directly onto this user's workflow with no redesign required.
- ICP A naturally graduates into ICPs B and C as the tool matures; the reverse adoption path is harder.
- Comp AI's FedRAMP coverage is 41% by their own admission; a tool that's deep in FedRAMP specifically serves ICP A meaningfully better than a breadth-first SaaS platform.
- Absent a named ICP, architectural decisions were fuzzy. Multiple pending questions (web UI, SaaS mode, continuous monitoring, framework expansion) resolve quickly with this ICP as the filter.

**Alternatives considered:**
- **ICP B as primary (defense contractor, CMMC 2.0 / DoD IL):** deferred. Requires Bedrock backend, CUI handling, and air-gap operation we cannot ship in v0. Acute pain, but longer tool-adoption cycle and harder to serve well at hackathon scale. Becomes primary at v1.5+ once CMMC overlay and Bedrock ship.
- **ICP C as primary (platform team at 1000+ engineer gov-contractor):** rejected for v0. Requires mature plugin ecosystem and multi-team coordination features we won't have for months. Will be well-served by the architecture we're building, but not as an early adopter.
- **No primary ICP (serve everyone):** explicitly rejected. This is how OSS compliance tools fail to find traction even with good code. A fuzzy buyer produces a plausible-to-many, essential-to-none tool.
- **SaaS companies pursuing SOC 2 as primary:** rejected. That market is well-served (Comp AI, Vanta, Drata); our gov-grade depth is wasted there.

---

## 2026-04-18 — Terraform/OpenTofu only at v0; source-type expansion as v1 priority `[scope]` `[architecture]`

**Decision:** v0 scans Terraform and OpenTofu source files (`.tf`) only. The v1 roadmap commits to source-type expansion in this order: Terraform Plan JSON (month 1), CloudFormation/CDK (month 2), Kubernetes manifests + Helm (month 3), Pulumi (month 4). Runtime cloud API scanning is v1.5+. The detector contract is already source-typed (`source="terraform"` is a field on the decorator) and the detector library folder structure accommodates parallel source types, so expansion is additive rather than a rearchitecture.

**Rationale:**
- A 4-day hackathon build has to pick one input modality and do it well. Two parsers plus two parallel detector sets doubles the work without doubling the demo impact.
- Terraform is the single largest input modality for ICP A (roughly 40–50% of SaaS companies with mature IaC), and OpenTofu is syntactically identical — one parser covers both.
- ICP A users pursuing first FedRAMP authorization disproportionately run their FedRAMP boundary as a dedicated deployment (often GovCloud) that is freshly Terraform-codified, which makes Terraform-only coverage more practically sufficient than a raw "what fraction of SaaS companies use Terraform" number would suggest.
- Being explicit about the v0 constraint, rather than implicit, sets correct expectations. An ICP A user with a mixed codebase knows whether Efterlev covers them today.
- The v1 expansion path is committed and sequenced by ICP A value, not by implementation ease. Source-type breadth matters more for adoption; control-count depth matters more for trust. Both grow in parallel.

**Alternatives considered:**
- **Ship multi-source support at v0 (Terraform + CloudFormation at minimum):** rejected. Doubles hackathon engineering work, dilutes the vertical-slice discipline, produces two half-working parsers rather than one complete one.
- **Ship CloudFormation instead of Terraform as the v0 input:** rejected. Smaller user base, same engineering cost, weaker demo story.
- **Runtime cloud API scanning at v0:** rejected. Different threat model (requires cloud credentials, crosses a trust boundary we deliberately don't cross at v0), much larger surface area, and produces evidence that users can't easily verify against source control.
- **Defer source-type expansion to v2:** rejected. Adoption penalty is too high. ICP A users with mixed IaC need a path from "this is for me someday" to "this is for me now," and that path is source-type expansion in early v1.

---

## 2026-04-19 — Pre-hackathon stack verification on Python 3.12 `[process]` `[tool-choice]`

**Decision:** Dep versions resolved by `uv sync` against the current `pyproject.toml` are the pre-hackathon baseline. `uv.lock` is committed.

**Verified today (Python 3.12.3, uv 0.8.17):**

- `uv sync` resolves cleanly. Key runtime versions: compliance-trestle 3.12.0, mcp 1.27.0, anthropic 0.96.0, pydantic 2.13.2, typer 0.24.1, python-hcl2 5.1.1, jinja2 3.1.6. All import without error.
- `scripts/trestle_smoke.py` loads the vendored NIST SP 800-53 Rev 5.2.0 catalog via `trestle.oscal.catalog.Catalog.oscal_read`. Walks the group tree correctly: 20 families, 324 top-level controls, 1,196 including enhancements. Each of the six hackathon target families (SC, IA, AU, CP, and the ones SC-8/SC-13 sit under) resolves.
- anthropic SDK 0.96.0 imports and instantiates. Model string `claude-opus-4-7` is structurally accepted by the SDK (no model-ID validation error).
- Minor observation for the hackathon loader primitive: trestle exposes `metadata.oscal_version` as a Pydantic `RootModel`, so a naive `print(md.oscal_version)` yields `__root__='1.1.3'` rather than the string. The internal `Control` / `Profile` mapper should unwrap via `.root`.

**Not verified today (requires user's terminal):**

- Live authenticated call to the Anthropic API with `claude-opus-4-7`. The sandbox session that ran the other smoke tests does not expose an `ANTHROPIC_API_KEY` to subprocesses. The smoke script completed the SDK wiring and failed cleanly on missing credentials, which is the correct behavior but does not confirm the hackathon API key works or that `claude-opus-4-7` is available on that key's plan.

**Action for the user before Day 1:** run the one-liner below on a shell that has `ANTHROPIC_API_KEY` set. Expected output is a short response containing "smoke ok" and no error. If `claude-opus-4-7` is rejected by the API (e.g. the key lacks plan access), fall back per the existing DECISIONS entry on model selection and note it here.

```bash
uv run python -c "from anthropic import Anthropic; r = Anthropic().messages.create(model='claude-opus-4-7', max_tokens=32, messages=[{'role':'user','content':'Reply with exactly: smoke ok'}]); print(r.model, '|', r.content[0].text)"
```

**Rationale for recording this rather than skipping:** honesty about what was verified and what wasn't keeps the pre-hackathon checklist credible. A green check we didn't actually earn would be worse than an open item.

---

## 2026-04-19 — FedRAMP Moderate OSCAL baseline source is blocked; options under review `[scope]` `[architecture]`

**Decision:** No decision yet. Logging the block so the next session's first action is settling this.

**Situation:** `CLAUDE.md`, `README.md`, `docs/dual_horizon_plan.md`, and `CONTRIBUTING.md` all reference `GSA/fedramp-automation` (path `dist/content/rev5/baselines/json/FedRAMP_rev5_MODERATE-baseline_profile.json`) as the source for the FedRAMP Moderate OSCAL profile. Pre-hackathon verification today found that URL returns 404 from both `github.com` and `raw.githubusercontent.com`. Public reporting indicates the repo was archived in mid-2025 and a subsequent release removed the OSCAL baseline content as FedRAMP transitioned toward the FedRAMP Machine-Readable (FRMR) format under the FedRAMP 20x initiative. `FedRAMP/docs` (live) now hosts FRMR documentation; it does not contain OSCAL baselines. `usnistgov/oscal-content` has the 800-53 catalog but no FedRAMP-specific profile at any path probed.

**What we did land today:** vendored the NIST SP 800-53 Rev 5 catalog into `catalogs/nist/`. A FedRAMP Moderate profile, however we obtain it, must resolve against this catalog, so vendoring it does not prejudice the choice below.

**Options under consideration (not ranked yet; needs human call):**

- **A. Pin to the last good pre-archive commit of `GSA/fedramp-automation`.** Recover the baseline from a historical tag or Wayback Machine, record the deprecation context in `catalogs/README.md`, and vendor that. Pros: minimal change to plan; one-time effort. Cons: we ship stale content relative to FedRAMP's current direction; updates are manual.
- **B. Construct the FedRAMP Moderate profile ourselves from published control lists.** The control selections are public. A hand-rolled OSCAL profile referencing the vendored 800-53 catalog is straightforward. Pros: full control over provenance; no dependency on a vanishing upstream. Cons: we take ownership of a thing FedRAMP used to publish; maintenance burden.
- **C. Treat FRMR as the primary FedRAMP-source input and emit OSCAL only at the output boundary.** Bigger architectural shift. Pros: aligns with where FedRAMP is actually going; differentiated positioning. Cons: out of scope for the hackathon; FRMR is a moving target and tool support is thin.
- **D. Defer the FedRAMP-specific profile; ship v0 against the NIST 800-53 baseline directly, profile-less.** Pros: unblocks the hackathon immediately; every detector already declares the controls it evidences. Cons: loses the "FedRAMP Moderate" framing of the demo.

**Pointers for whoever decides:** `COMPETITIVE_LANDSCAPE.md` still positions Efterlev as FedRAMP-focused, so option D weakens the pitch. `README.md`'s coverage table is per-control, not per-profile, so it doesn't need to change under any option. `LIMITATIONS.md` does not mention the profile source and so is unaffected.

---

## 2026-04-19 — MCP stdio transport verified with FastMCP on mcp 1.27.0 `[architecture]` `[process]`

**Decision:** FastMCP (`mcp.server.fastmcp.FastMCP`) is the minimum-viable server shape for v0. Stdio is the transport. Both are confirmed working on this Python 3.12 install.

**Verified today (mcp 1.27.0):**

- `scripts/mcp_smoke_server.py` registers two tools (`echo`, `add_two_numbers`) via the `@mcp.tool()` decorator and runs over stdio without configuration.
- `scripts/mcp_smoke_client.py` spawns the server as a subprocess, initializes a `ClientSession`, enumerates tools, and invokes each one. Both calls return the correct result. Protocol version negotiated: `2025-11-25`.
- Server init payload exposes `serverInfo.name="efterlev-smoke"` — this is how external Claude Code discovers the server's identity. The real `src/efterlev/mcp_server/` should follow the same pattern with `name="efterlev"`.

**Not verified today (requires user):**

- Second Claude Code session discovering and calling the smoke server live. The in-process client proves the transport; the live discovery is a separate trust claim (Claude Code's MCP client handles tool discovery, argument schema validation, and result rendering in ways our in-process client does not exercise). Instructions are in `scripts/README.md` under "Live Claude Code verification (manual)".

**Rationale for FastMCP over the lower-level `mcp.server.Server`:** FastMCP's decorator pattern produces agent-legible tool schemas from Python type hints with zero boilerplate. That is exactly the shape we want for the real primitive registration — our primitive decorator can wrap `@mcp.tool()` and add provenance emission without rewriting the MCP plumbing.

**Alternatives considered:**

- **Lower-level `mcp.server.Server`:** more control, more boilerplate, no clear advantage for our use case. Reconsider only if FastMCP's schema generation doesn't play well with our Pydantic input/output models (we'll find out Day 2).

---

## 2026-04-19 — Pivot to KSI-native, FRMR-first; OSCAL demoted to v1 output `[architecture]` `[scope]` `[positioning]`

**Decision:** Efterlev's primary internal abstraction is the FedRAMP 20x **Key Security Indicator (KSI)**, not the 800-53 control. Its primary output format is **FRMR-compatible JSON** (from `FedRAMP/docs`), not OSCAL. NIST 800-53 Rev 5 remains the underlying catalog — each KSI references 800-53 controls, and detectors still evidence those controls — but the user-facing surface and the primary output both speak KSIs and FRMR. OSCAL output generation is demoted to a v1 secondary format for users transitioning Rev5 submissions and for downstream OSCAL-Hub-style consumers.

**This entry explicitly reverses the 2026-04-18 decision "OSCAL as output, not internal model."** The OSCAL-as-first-class-output framing no longer matches where FedRAMP is going or where our ICP is landing. The internal-model-vs-output-boundary discipline from that earlier entry is preserved and stays correct; what changes is *which* output format is primary.

**Rationale:**

1. **FedRAMP itself is moving.** Phase 1 of FedRAMP 20x completed in late 2025 with 13 Low authorizations; Phase 2 Moderate pilot is underway and Phase 2 entered pilot in November 2025 with an initial end date of 2026-03-31. In 2025 FedRAMP processed 100+ Rev5 authorizations with zero OSCAL-structured submissions, and no 20x Phase 1 participant used OSCAL to structure required machine-readable materials. FRMR (FedRAMP Machine-Readable) is the format FedRAMP 20x is shipping, and it is actively maintained at `FedRAMP/docs`. Betting the internal model and primary output on OSCAL was betting on a pace of adoption that the field has not produced. Betting on KSIs + FRMR aligns with what FedRAMP's own authorization pipeline now accepts.

2. **Architectural alignment.** Our thesis — "evidence over narrative, outcomes over process, deterministic scanner output primary, LLM reasoning secondary" — maps to KSIs directly. KSIs are explicitly outcome-based measurable indicators ("Encrypt or otherwise secure network traffic"; "Enforce multi-factor authentication using methods that are difficult to intercept or impersonate"). OSCAL's SSP narrative model asks for process and implementation descriptions, which are a less-good fit for what a code scanner can honestly produce. FRMR attestations ("here is the evidence that this outcome is achieved, citing Terraform line X") are exactly what we generate; SSP narratives ("here is how we implement the control") are not.

3. **ICP alignment.** Our ICP is a SaaS company (50–200 engineers) starting its first FedRAMP effort in 2026 with a committed federal deal on the line. A new-in-2026 authorization targets 20x, which is KSI-native. Serving this user well means speaking KSIs in the CLI, the agent output, and the report — not speaking 800-53 control numbers and OSCAL. The primary ICP entry at `docs/icp.md` supports this directly: their day-one experience improves when it lands in the language FedRAMP 20x is actually asking them for.

4. **Market positioning.** No OSS tool is KSI-native today. Comp AI is not; their FedRAMP coverage (41% in their own demo) is Rev5-era, not 20x. RegScale OSCAL Hub is deep-OSCAL and has real architectural debt to work through on FRMR. Being KSI-native from day one is a differentiator that is currently unclaimed. The "dev-tool-shaped positioning nobody else is occupying" argument in `COMPETITIVE_LANDSCAPE.md` is now sharpened by "KSI-native positioning nobody else is occupying *yet*."

5. **Engineering simplicity.** FRMR is a single JSON file with a published JSON Schema (`FedRAMP.schema.json`, draft 2020-12). Pydantic reads it directly — no specialized library needed, no complex profile/catalog/SSP model hierarchy to wrestle with. The hackathon saves engineering effort that would otherwise have gone into OSCAL generator-primitive plumbing and spends it on the detector library instead, which is the moat. Adding OSCAL generators in v1 is additive (one more generator primitive) rather than rearchitectural (the internal model is format-agnostic by design).

6. **Honest claims.** "We evidence KSI-SVC-SNT via Terraform detection of TLS configuration on ALB listeners" is a more honest claim than "we evidence SC-8, whose full implementation includes procedural aspects we cannot see from code." KSIs are designed around outcomes we can actually detect. This tightens the evidence-vs-claim discipline at the contract level rather than only in documentation.

**Alternatives considered:**

- **Stay OSCAL-primary and attempt to recover the archived FedRAMP OSCAL profile.** Rejected. `GSA/fedramp-automation` was archived mid-2025 and its OSCAL baselines removed as FedRAMP transitioned to FRMR. Recovering from Wayback Machine or a pre-archive tag is possible but ships stale content that FedRAMP no longer maintains, and the positioning ("we produce OSCAL primarily") bets against where FedRAMP is going. The previous DECISIONS entry ("FedRAMP Moderate OSCAL baseline source is blocked; options under review") listed this as option A; we are rejecting it here.
- **Drop OSCAL entirely.** Rejected. RFC-0024 proposed a September 2026 machine-readable floor for Rev5 submissions; NOTICE-0009 (2026-03-25) softened the date and moved formalization into CR26 (due end of June 2026, valid through 2028-12-31), but the direction of travel stands. Tools like OSCAL Hub (donated to the OSCAL Foundation in late 2025) exist and serve a real constituency. Users mid-Rev5-transition need OSCAL output; cutting it entirely forecloses that user. OSCAL lands in v1 as a secondary output for those users.
- **Support both FRMR and OSCAL equally at v0.** Rejected. "Primary format" is a strategy choice, not a feature list. Supporting both equally produces a tool with no clear positioning, double the Day 2–3 generator engineering, and muddled messaging. Primary means primary; we pick.
- **Treat FRMR as input only (consume KSI definitions) and keep OSCAL as primary output.** Considered briefly. Rejected because it inverts the positioning mismatch: we would produce OSCAL artifacts that map back to KSIs we derived from FRMR — which is more work than generating FRMR directly and lands in a format FedRAMP 20x reviewers are not asking for.

**Known open item (flagged on the pivot, not resolved by it):** FRMR 0.9.43-beta does not list SC-28 (encryption at rest) in any KSI's `controls` array, and no indicator `statement` references "at rest." Our encryption-at-rest detector area therefore has `[TBD]` in the KSI column of `CLAUDE.md` and `README.md` with KSI-SVC-VRI (Validating Resource Integrity, SVC theme) marked as the nearest thematic fit. Day 1 resolves this: either accept KSI-SVC-VRI with an honest docstring caveat, reframe the detector around integrity, or open an issue on `FedRAMP/docs` for a missing KSI. Do not invent a KSI.

**What did not change (so this entry's scope is clear):**
- Primitive / detector / agent three-way architecture separation
- Evidence-vs-Claim discipline in the data model
- Provenance model (append-only, content-addressed, versioned)
- MCP as the agent-exposed interface; FastMCP as the server shape
- Claude Code / Anthropic direct API at v0; AWS Bedrock as v1 second backend
- Apache 2.0 license, governance model, contribution posture
- Primary ICP (first-FedRAMP SaaS, 50–200 engineers); ICPs B and C as secondary
- Six hackathon detection areas (their KSI mappings are added; the detection areas themselves are the same six)
- Terraform/OpenTofu as v0 input source; AWS as v0 cloud
- 4-day demo flow structure and the meta-loop demo moment
- govnotes as the demo target
- CMMC 2.0 as v1 second framework; DoD IL as v1.5+

---



```
## YYYY-MM-DD — Short decision summary `[tag]` `[tag]`

**Decision:** What was decided.

**Rationale:** Why.

**Alternatives considered:**
- Alt 1 — why rejected
- Alt 2 — why rejected
```
