# CLAUDE.md — Efterlev

This file is your persistent context. Read it in full at the start of every session.

---

## What we're building

**Efterlev** is a repo-native, agent-first compliance scanner for FedRAMP 20x and DoD Impact Levels. It lives in the developer's codebase and CI pipeline — not in a dashboard — and it produces code-level findings, remediation diffs, and FRMR-compatible validation data (the machine-readable format FedRAMP 20x is standardizing on) for downstream consumption. OSCAL generation is a v1 secondary output format for users transitioning Rev5 submissions or feeding downstream tools like RegScale's OSCAL Hub.

Efterlev's primary internal abstraction is the **Key Security Indicator (KSI)** — the outcome-based, measurable unit FedRAMP 20x built the pilot around. Detectors evidence KSIs; KSIs map to 800-53 controls; 800-53 remains the underlying catalog. The user-facing surface speaks KSIs.

The name "Efterlev" is a shortening of the Swedish *efterlevnad* (compliance). Pronounce it "EF-ter-lev."

**Primary user (the ICP lens for every product decision):** a SaaS company (50–200 engineers) pursuing its first FedRAMP Moderate authorization, with a committed federal deal on the line. Full ICP at `docs/icp.md` — read it before proposing features, because the ICP is how we decide what Efterlev does and doesn't do.

The full plan lives in `docs/dual_horizon_plan.md`. **Read it before proposing any architectural change.** Competitive positioning lives in `COMPETITIVE_LANDSCAPE.md` — read that before making any positioning-adjacent claim.

We are building this for a 4-day hackathon demo, then continuing as an open-source project. The architecture is designed so that nothing built in the hackathon layer needs to be thrown away to build the v1 layer.

---

## Non-negotiable principles

These override local convenience. If you feel tempted to violate one, stop and ask.

1. **Evidence before claims.** Deterministic scanner output is primary, high-trust, and citable. LLM-generated content (narratives, mappings, rankings, remediation proposals) is secondary, carries confidence levels, and is explicitly marked "DRAFT — requires human review" in output. The two classes are visible in the data model, the FRMR output, and every rendered report.
2. **Provenance or it didn't happen.** Every generated claim — finding, narrative, mapping, remediation — emits a provenance record linking it to its upstream sources (detector output, evidence records, LLM calls). No exceptions, not for speed, not for demo polish.
3. **FRMR as primary output; OSCAL as secondary v1 output. Internal model is KSI-shaped.** The user-facing layer is Indicators (KSIs) and Themes; 800-53 Controls remain first-class because KSIs reference them, but they are the underlying layer, not the primary surface. FRMR-compatible JSON is what the Documentation Agent produces at v0. OSCAL output generators are v1 additions for users transitioning Rev5 submissions and for downstream OSCAL-Hub-style consumers. The internal data model is our own Pydantic types, shaped around our needs; FRMR and OSCAL are both produced at the output boundary, not used as internal representations.
4. **Detectors are the moat; primitives are the interface.** The detection library is a community-contributable asset. Each detector is a self-contained folder a contributor can add without touching the rest of the codebase. Primitives are the stable, MCP-exposed surface over which agents reason.
5. **Agent-first, pragmatically.** Every primitive is exposed via our MCP server from the moment it exists. External agents (other people's Claude Code, third-party tools) can discover and call every primitive. Our own agents prefer the MCP interface because it proves the architecture, but direct Python imports are acceptable when they materially improve performance or reliability. Don't be religious about it; the useful, demoable solution is what matters.
6. **Demo a slice, architect for the whole.** The MVP is narrow (six controls, one cloud, one IaC tool). The architecture must make adding the next 50 detectors obvious, not painful.
7. **Drafts, not authorizations.** Efterlev never claims to produce an ATO, a pass, or a guarantee of compliance. It produces drafts that accelerate the human/3PAO process. This is not hedging; it's the truth, and it's the only claim that survives serious scrutiny.

---

## Tech stack

- **Language:** Python 3.12
- **Dependency management:** `uv`
- **Typing:** Pydantic v2 for all primitive I/O. No untyped dicts crossing a primitive boundary.
- **FRMR:** `FRMR.documentation.json` vendored from `FedRAMP/docs` into `catalogs/frmr/`. It is a single authoritative JSON file (`info`, `FRD`, `FRR`, `KSI`) — substantially simpler than OSCAL's nested model hierarchy. Load with Pydantic directly; no specialized library required. Validate against `FedRAMP.schema.json` (JSON Schema draft 2020-12) before returning output.
- **OSCAL (v0 input only):** `compliance-trestle` for loading the vendored NIST SP 800-53 Rev 5 catalog, which every KSI indicator references via its `controls` field. Trestle is not used for FedRAMP-specific profiles (no current upstream source after the GSA/fedramp-automation archive). OSCAL *output* generation is a v1 roadmap item; hand-rolled Pydantic generators where trestle's generation APIs are clunky — document reason in `DECISIONS.md`.
- **MCP:** Official Anthropic Python SDK for MCP server authoring. Stdio transport.
- **Agent inference:** Anthropic Python SDK. Default model `claude-opus-4-7`. Switch to `claude-sonnet-4-6` only if we hit latency issues during demo. **Centralize client instantiation in `src/efterlev/llm/__init__.py` — do not scatter `anthropic.Anthropic()` calls across agent files.** This is the cheap hedge for the v1 pluggable-backend work; see `DECISIONS.md`.
- **LLM backends (v1):** AWS Bedrock committed as the second backend via an `LLMClient` abstraction. This is not a hackathon deliverable — v0 wires to the Anthropic SDK directly — but v0 code structure must not foreclose it.
- **Storage:** SQLite for the provenance graph and metadata. Content-addressed blob store on disk under `.efterlev/store/` (SHA-256 filenames). Timestamped and versioned — evidence records are appended, never overwritten.
- **CLI:** Typer. Single entry point: `efterlev`.
- **IaC parsing:** `python-hcl2` for Terraform.
- **Code scanning:** `semgrep` via subprocess.
- **Testing:** `pytest`. Every primitive and detector has ≥1 happy-path and ≥1 error-path test. No coverage targets — we optimize for confidence, not numbers.
- **Formatting:** `ruff` for lint + format. `mypy --strict` on `src/efterlev/primitives/`, `src/efterlev/detectors/`, `src/efterlev/frmr/`, `src/efterlev/oscal/`.
- **Docs:** MkDocs Material.

---

## Repository layout

```
efterlev/
├── CLAUDE.md                          # this file
├── README.md                          # user-facing
├── CONTRIBUTING.md                    # human-contributor onboarding
├── DECISIONS.md                       # running log of non-trivial choices — APPEND-ONLY
├── LIMITATIONS.md                     # judge-facing + user-facing
├── THREAT_MODEL.md                    # security posture
├── COMPETITIVE_LANDSCAPE.md           # honest positioning
├── LICENSE                            # Apache 2.0
├── docs/
│   ├── dual_horizon_plan.md           # the full plan
│   ├── architecture.md
│   ├── scope.md
│   └── primitives.md                  # auto-generated from decorator metadata
├── src/efterlev/
│   ├── models/                        # our internal Pydantic types
│   │   ├── indicator.py               # Indicator (a KSI), Theme, Baseline
│   │   ├── control.py                 # Control, ControlEnhancement (800-53, referenced by KSIs)
│   │   ├── evidence.py                # Evidence (deterministic)
│   │   ├── claim.py                   # Claim (LLM-reasoned)
│   │   ├── finding.py
│   │   ├── mapping.py
│   │   ├── provenance.py
│   │   └── attestation_draft.py       # internal AttestationDraft before FRMR serialization
│   ├── frmr/                          # FRMR loader + validator + generator (primary output)
│   ├── oscal/                         # 800-53 catalog loader via trestle; OSCAL generator is v1
│   ├── detectors/                     # the detection library (community-contributable)
│   │   ├── base.py                    # Detector base class + decorator
│   │   └── aws/
│   │       ├── encryption_s3_at_rest/
│   │       │   ├── detector.py
│   │       │   ├── mapping.yaml
│   │       │   ├── evidence.yaml      # our internal schema, not FRMR or OSCAL
│   │       │   ├── fixtures/          # should-match + should-not-match samples
│   │       │   └── README.md
│   │       └── ...
│   ├── primitives/                    # MCP-exposed agent-legible capabilities
│   │   ├── scan/
│   │   ├── map/
│   │   ├── evidence/
│   │   ├── generate/                  # FRMR + HTML generators at v0; OSCAL generator in v1
│   │   └── validate/
│   ├── mcp_server/
│   ├── agents/
│   │   ├── base.py
│   │   ├── gap.py                     # + gap_prompt.md
│   │   ├── documentation.py           # + documentation_prompt.md
│   │   └── remediation.py             # + remediation_prompt.md
│   ├── provenance/
│   └── cli/
├── catalogs/                          # inputs: FRMR + 800-53 Rev 5 catalog
│   ├── frmr/                          # FedRAMP FRMR JSON + schema
│   └── nist/                          # NIST SP 800-53 Rev 5 catalog (OSCAL JSON)
├── demo/govnotes/                     # sample target app
└── tests/
```

When adding new detectors, match the cloud/source folder. When adding primitives, match the capability verb (`scan`, `map`, `evidence`, `generate`, `validate`). If it doesn't fit, propose a new subfolder in chat before creating it.

---

## The detector contract

A detector is a self-contained artifact. One folder per detector. A contributor can add a new detector without reading the rest of the codebase. This is the #1 design commitment for long-term project health.

Each detector folder contains:

- **`detector.py`** — pure function, typed input/output. Reads source material (IaC files, manifests, etc.), emits `Evidence` records.
- **`mapping.yaml`** — which KSI(s) this detector evidences, plus the underlying 800-53 control(s) those KSIs reference. Multi-target mappings are fine (one detector can evidence multiple KSIs and multiple controls).
- **`evidence.yaml`** — template describing the shape and semantics of evidence this detector produces. Our internal schema, not FRMR or OSCAL.
- **`fixtures/`** — `should_match/` and `should_not_match/` IaC samples the test harness runs against.
- **`README.md`** — human-readable: what this detector checks, what it proves, what it does not prove, known limitations.

Detector IDs are capability-shaped (what the detector checks), not control-shaped. KSIs think in capabilities; IDs like `encryption_s3_at_rest` age better than IDs like `sc_28_s3_encryption` as the KSI ↔ control mapping evolves.

Example:

```python
# detectors/aws/encryption_s3_at_rest/detector.py
from efterlev.detectors.base import detector
from efterlev.models.evidence import Evidence

@detector(
    id="aws.encryption_s3_at_rest",
    ksis=["KSI-SVC-VRI"],             # Validating Resource Integrity (nearest KSI; see README.md)
    controls=["SC-28", "SC-28(1)"],   # underlying 800-53 controls
    source="terraform",
    version="0.1.0",
)
def detect(tf_resources: list[TerraformResource]) -> list[Evidence]:
    """
    Detect S3 bucket encryption configuration at rest.

    Evidences (800-53):  SC-28 (Protection at Rest), SC-28(1) (Cryptographic Protection).
    Evidences (KSI):     KSI-SVC-VRI (Validating Resource Integrity) — partial.
    Does NOT prove:      key management practices, rotation, BYOK — those are
                         SC-12/SC-13 / KSI-SVC-ASM territory. This detector only
                         evidences the infrastructure layer of at-rest encryption,
                         not the procedural layer.

    Note: FRMR 0.9.43-beta does not list SC-28 in any KSI's `controls` array, so
    the KSI mapping above is a judgment call grounded in FedRAMP's stated intent
    (cryptographic means to prevent unauthorized access to federal customer data
    at rest). Re-evaluate when FRMR GA ships.
    """
    ...
```

The docstring's "does NOT prove" section is required. This is the evidence-vs-claims discipline at the detector level — we name what we've actually verified and what we haven't.

---

## The primitive contract

Primitives are the MCP-exposed agent interface. ~15–25 total at v1. Small and stable.

**Two classes of primitives, different contracts:**

**Deterministic primitives** — scan, map, validate, parse, hash, serialize. Pure where possible. Side-effecting primitives (write files, open PRs) are flagged. Tests cover happy path + edge cases. Example:

```python
@primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
def scan_terraform(input: ScanTerraformInput) -> ScanTerraformOutput:
    """Run all applicable detectors against a Terraform source tree."""
```

**Generative primitives** — narrative synthesis, mapping proposal, remediation suggestion. LLM-backed. Output carries confidence levels and a "requires human review" flag. Tests are harder; we use snapshot comparisons and known-good fixtures. Example:

```python
@primitive(capability="generate", side_effects=False, version="0.1.0", deterministic=False)
def generate_ssp_narrative(input: GenerateNarrativeInput) -> GenerateNarrativeOutput:
    """Draft SSP narrative for a control, grounded in its evidence records."""
```

**Shared rules for both classes:**

- Verb-noun snake_case name
- One Pydantic input model, one Pydantic output model
- Docstring states intent, side effects, deterministic/generative, external dependencies
- Emits a provenance record via decorator machinery — you do not write provenance code inside the function body
- Auto-registered with the MCP server by the decorator
- No `print`; use the standard logger
- Raises typed exceptions from `efterlev.errors`, never bare `Exception`
- Before adding a new primitive, check `docs/primitives.md` for overlap. If something close exists, extend or rename — don't add a parallel function.

---

## The agent contract

Every agent:

- Subclasses `efterlev.agents.base.Agent`
- Has a system prompt in a sibling `.md` file (e.g. `gap.py` → `gap_prompt.md`). Prompts are product code. Do not inline them as Python strings.
- Consumes primitives via the MCP tool interface by default. Direct imports from `efterlev.primitives.*` are allowed when MCP round-tripping adds no value; flag the choice in the agent's docstring.
- Produces a typed output artifact on our internal model (e.g. `GapReport`, `AttestationDraft`, `RemediationProposal`). FRMR and OSCAL serialization are separate generator steps, not the agent's job.
- Logs every tool call, model response, and final artifact to the provenance store
- Is invokable standalone from the CLI: `efterlev agent <n> [options]`

**When you write or revise an agent's system prompt, surface the full diff in chat for review before committing.** Agent prompts are the product's brain; they deserve human sign-off even when code doesn't.

---

## Evidence vs. claims: the data model

Two distinct types, treated differently throughout the system.

```python
class Evidence(BaseModel):
    """Deterministic, scanner-derived, high-trust."""
    evidence_id: str                    # sha256 of canonical content
    detector_id: str                    # "aws.encryption_s3_at_rest"
    ksis_evidenced: list[str]           # ["KSI-SVC-VRI"] — primary indicator(s)
    controls_evidenced: list[str]       # ["SC-28", "SC-28(1)"] — underlying 800-53
    source_ref: SourceRef               # file + line + commit hash
    content: dict                       # detector-schema-shaped
    timestamp: datetime

class Claim(BaseModel):
    """LLM-reasoned, requires human review."""
    claim_id: str                       # sha256 of canonical content
    claim_type: Literal["narrative", "mapping", "remediation", "classification"]
    content: str | dict
    confidence: Literal["low", "medium", "high"]
    requires_review: bool = True        # always true at v0
    derived_from: list[str]             # evidence_ids and/or other claim_ids
    model: str                          # "claude-opus-4-7"
    prompt_hash: str                    # hash of the system prompt used
    timestamp: datetime
```

Every rendered output — HTML report, FRMR artifact, OSCAL artifact, terminal summary — visually distinguishes Evidence from Claims. Evidence cites raw sources. Claims carry the "DRAFT — requires human review" marker. An auditor reading our output can always tell which is which.

---

## Provenance model

Every claim is a node in a directed provenance graph. Edges point from derived claims to upstream sources.

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
- Records are immutable and append-only. New evidence for a KSI creates a new record; it does not overwrite the old one. This supports the v1 drift-detection story.
- `efterlev provenance show <record_id>` walks the chain. Every new record type must render sensibly.

When you implement a primitive or agent that generates records, **write the provenance walk test first**. If the chain doesn't resolve end-to-end, the feature isn't done.

---

## FRMR and OSCAL conventions

FRMR is the primary output format at v0. OSCAL is a secondary output format planned for v1. Both are **output**, not internal representations.

**FRMR (primary, v0):**

- **Input:** `catalogs/frmr/FRMR.documentation.json` vendored from `FedRAMP/docs`. Loaded with Pydantic at startup into our internal `Indicator`, `Theme`, and related types. KSI indicators' `controls` fields tie each KSI to one or more 800-53 controls, which the 800-53 loader resolves.
- **Output:** FRMR-compatible JSON artifacts (primarily `AttestationDraft`-shaped validation data) produced by dedicated generator primitives in `primitives/generate/`. Plus HTML and markdown alongside.
- **Validation:** Every generated FRMR artifact is validated against `catalogs/frmr/FedRAMP.schema.json` before return. `efterlev.primitives.validate.validate_frmr` is called inside the generator — if validation fails, the generator raises.

**OSCAL (input at v0, output at v1):**

- **Input:** NIST SP 800-53 Rev 5 catalog at `catalogs/nist/` is loaded via `compliance-trestle` into our internal `Control` and `Catalog` types. FedRAMP-specific OSCAL profiles are not loaded at v0; no current canonical upstream source after the GSA/fedramp-automation archive.
- **Output (v1):** OSCAL Assessment Results, partial SSP, POA&M generators are roadmap items for Rev5 transition users. Validation against the NIST OSCAL schemas will run inside the generator before return.

When in doubt about FRMR modeling, default to the structure described in `catalogs/frmr/FRMR.md`. When OSCAL generators land in v1 and you need reference material, the `usnistgov/oscal-content` repo holds the canonical examples.

---

## Detection scope (hackathon MVP — locked)

Six detection areas. **Do not add areas outside this set without asking** — scope creep here is how we lose the hackathon.

KSIs below are from FRMR 0.9.43-beta (vendored at `catalogs/frmr/FRMR.documentation.json`). Each detection area evidences one or more KSIs and the underlying 800-53 controls those KSIs reference.

| Detection area | KSI (FRMR 0.9.43-beta)                          | 800-53         | Signal source             |
| -------------- | ----------------------------------------------- | -------------- | ------------------------- |
| Encryption at rest | `[TBD]` — closest: KSI-SVC-VRI (Validating Resource Integrity); see note below | SC-28, SC-28(1) | S3/RDS/EBS encryption     |
| Transmission confidentiality | KSI-SVC-SNT (Securing Network Traffic)  | SC-8           | TLS config, ALB listener  |
| Cryptographic protection | KSI-SVC-VRI (Validating Resource Integrity); also reinforces KSI-SVC-SNT | SC-13          | Algorithms, FIPS mode     |
| MFA enforcement | KSI-IAM-MFA (Enforcing Phishing-Resistant MFA) | IA-2           | IAM policy conditions     |
| Event logging & audit generation | KSI-MLA-LET (Logging Event Types), KSI-MLA-OSM (Operating SIEM Capability) | AU-2, AU-12 | CloudTrail scope          |
| System backup | KSI-RPL-ABO (Aligning Backups with Objectives)    | CP-9           | RDS backups, S3 versioning|

**On the SC-28 / encryption-at-rest `[TBD]`:** FRMR 0.9.43-beta does not list SC-28 in any KSI's `controls` array, and no indicator's `statement` mentions "at rest" explicitly. KSI-SVC-VRI ("Use cryptographic methods to validate the integrity of machine-based information resources") is the nearest thematic fit — it lives in the Service Configuration theme whose overview references "FedRAMP encryption policies" — but it nominally maps to SC-13 (integrity via crypto), not SC-28 (confidentiality of data at rest). Treat the mapping as a judgment call pending resolution. Day 1 should either: (a) accept KSI-SVC-VRI with an honest docstring caveat, (b) propose the detection area be reframed around integrity rather than confidentiality, or (c) surface the gap to FedRAMP via an issue on `FedRAMP/docs`. Do not invent a KSI that does not exist.

**On KSI-IAM-MFA:** the indicator requires *phishing-resistant* MFA (FIDO2/WebAuthn tier). Our detector only proves the IAM policy condition `aws:MultiFactorAuthPresent` is enforced. That's MFA-presence, not phishing-resistance. The detector README must name this gap.

**On KSI-RPL-ABO:** the indicator is about *alignment* of backups with recovery objectives — a claim about intent, not just mechanics. Our detector proves backups are enabled; "aligned with objectives" requires procedural evidence we cannot see from Terraform.

These detection areas were chosen because the infrastructure layer is genuinely dispositive — a detector can honestly say "the encryption configuration is present" without overclaiming the full KSI (including the procedural aspects). Detector `README.md` files must name the layer they evidence and the layer they do not.

**Explicitly deferred to v1+:**

- AC-2, AC-3, AC-6, AC-17 (identity/access controls requiring procedural evidence)
- AU-3 (audit record content — requires log schema inspection)
- CM-2, CM-6 (baseline configuration — requires procedural evidence)
- RA-5, SI-2, SI-4 (vulnerability management and monitoring)
- SC-7 (boundary protection — partially detectable but complex)
- IA-5 (authenticator management — partially detectable)
- All AT-\*, PL-\*, PS-\*, PM-\* (pure policy/procedural controls)
- Any control requiring runtime cloud API calls (v1+)

---

## What we are explicitly NOT building (hackathon)

Refuse scope expansions into:
- Input sources other than Terraform/OpenTofu (`.tf` files). No CloudFormation, AWS CDK, Pulumi, Kubernetes manifests, or runtime cloud API scanning at v0. All are v1 priorities, sequenced in `docs/dual_horizon_plan.md` §3.1.
- Real cloud account scanning (we read Terraform, we don't call AWS APIs)
- Continuous monitoring / drift daemon (v1)
- Adversarial Auditor Agent (v1 roadmap)
- Cross-framework mapping beyond FedRAMP 20x Moderate (CMMC 2.0 is the v1 second framework)
- GDPR, HIPAA, PCI, SOC 2, ISO 27001 (explicitly out — different tools do this)
- **OSCAL output generators at v0.** FRMR is the v0 primary output. OSCAL generation lands in v1 for users transitioning Rev5 submissions and for OSCAL-Hub-style downstream consumers.
- Web UI beyond generated static HTML reports
- Authentication/multi-tenancy (local CLI tool only)
- Real PR creation against real repos (local diff generation is the hackathon demo)

If the user asks for any of these, point to this list and confirm they want to trade it against an MVP item.

---

## Quality bar

- **Every detector:** typed I/O, docstring with "proves/does not prove," fixtures for should-match and should-not-match, passing tests.
- **Every primitive:** typed I/O, docstring, ≥1 happy test, ≥1 error test, FRMR (and in v1, OSCAL) validation on output where applicable, provenance record emitted.
- **Every agent:** system prompt in its own file, provenance-emitting, CLI-invokable, one end-to-end test against the demo repo.
- **Every commit:** `ruff` clean, `mypy --strict` clean on core paths, tests passing.
- **Every non-trivial decision:** appended to `DECISIONS.md` with date, decision, rationale, alternatives considered.

---

## How we work together

I'm solo, timeboxed, and relying on you heavily. Optimize for my throughput over your autonomy.

- **Vertical slice first, then replicate.** Day 1 builds one detector (`aws.encryption_s3_at_rest`) end-to-end through scan → evidence → provenance → CLI output. Days 2–4 replicate for five more, add agents, add polish. We do not build the whole framework before the first working detector.
- **Primitive-of-the-cycle rhythm.** We agree on the next primitive's contract in chat before you implement. You implement + test. I review. Move on.
- **Surface architectural questions immediately.** If you see a fork in the road, stop and ask. Do not silently pick and refactor later.
- **Prefer small PRs.** If a change touches more than three files outside of pure additions, flag it.
- **When stuck, say so.** If FRMR modeling, trestle behavior with the 800-53 catalog, or an MCP quirk is blocking you, surface it rather than working around it silently.
- **Maintain `DECISIONS.md`.** This is judge-facing and contributor-facing. Every non-obvious choice belongs there.
- **Regenerate `docs/primitives.md`** from decorator metadata after every primitive addition (`efterlev docs regenerate`).

---

## Demo target (the thing we optimize for)

The 4-day demo is this command sequence, end to end:

```bash
efterlev init --target ./demo/govnotes --baseline fedramp-20x-moderate
efterlev scan                              # produces evidence for KSIs (and 800-53 controls)
efterlev agent gap                         # classifies KSI status; HTML report
efterlev agent document                    # drafts FRMR-compatible attestation JSON + HTML
efterlev agent remediate --ksi KSI-SVC-VRI # proposes a Terraform diff fixing a gap
efterlev provenance show <record_id>
```

Plus: a second Claude Code session connecting to our MCP server and calling a primitive live. This is the architectural proof.

If a feature does not directly serve this flow or the architectural story behind it, defer it.

---

## Never do

- Never commit real secrets, API keys, or production data. The demo repo is synthetic.
- Never return FRMR (or, in v1, OSCAL) that hasn't been validated against its schema.
- Never generate a Claim without citing the Evidence records it derives from.
- Never claim the tool produces an ATO, a pass, or a guarantee of compliance. Drafts and findings only.
- Never add a dependency without a line in `DECISIONS.md` explaining why.
- Never expand the detection scope beyond the six areas above without explicit approval.
- Never mix Evidence and Claims in a way that loses their distinction — in the data model, in the UI, or in FRMR/OSCAL output.
- Never claim a detector proves more than it actually does. The "does NOT prove" section of the detector docstring is as important as the "does prove" section.
- Never invent a KSI ID that does not appear in the vendored FRMR. If coverage is genuinely missing, mark `[TBD]` and surface the gap; do not paper over it.

---

## References

- `docs/dual_horizon_plan.md` — full plan, including day-by-day schedule, demo script, and post-hackathon roadmap
- `docs/icp.md` — the Ideal Customer Profile; lens for every product decision
- `docs/scope.md` — the MVP contract
- `docs/architecture.md` — deeper architectural detail
- `DECISIONS.md` — running decision log
- `LIMITATIONS.md` — honest scope of what the tool does and doesn't do
- `THREAT_MODEL.md` — security posture for the tool itself
- `COMPETITIVE_LANDSCAPE.md` — positioning against Comp AI, RegScale OSCAL Hub, and others

When any of those conflict with this file, this file wins and we update the others.
