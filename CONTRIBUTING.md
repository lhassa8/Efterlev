# Contributing to Efterlev

> **v1 status (2026-04-22): external contributions paused.** Efterlev is in closed development through v1 (private repo, no public announcement). External detector/primitive/agent contributions are paused during this period; the architecture continues to support them, and this document stays authoritative for when the repo reopens. If you are an evaluating customer with private-repo access under NDA and want to contribute an internal detector or bug fix, contact the maintainer directly — the contribution path is the same as documented below, with review scoped to the engagement. Reopening timing is gated on first customer engagement or Month 6, whichever comes first. See `DECISIONS.md` 2026-04-22.

We want contributors. This document is the path from curiosity to merged PR. It is written for a human developer, not for Claude Code — that's what `CLAUDE.md` is for.

---

## The short version

- Five-minute path: clone, install, run tests, see them pass.
- One-hour path: pick an issue labeled `good first issue`, add a detector or fix a bug, open a PR with a passing test.
- Most valuable contribution type right now: new detectors for FedRAMP Moderate controls on the roadmap.
- Questions? Open a [GitHub Discussion](https://github.com/lhassa8/efterlev/discussions) before writing much code.

---

## Five-minute path: get a working environment

```bash
# Clone
git clone https://github.com/lhassa8/efterlev.git
cd efterlev

# Install (uv is fast; use pip if you prefer)
uv sync

# Run tests
uv run pytest

# Run the CLI against the demo repo
uv run efterlev init --target demo/govnotes --baseline fedramp-20x-moderate
uv run efterlev scan
```

If this works, you're ready to contribute. If it doesn't, open an issue — a broken first-run experience is a bug we want to hear about.

Requirements:
- Python 3.12+
- `uv` (optional but recommended): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- An Anthropic API key only if you want to run the generative agents locally. Not needed for detector work or tests.

---

## Where contributions fit

The project has a layered architecture. Most contributions land in one of these layers:

**Detectors** — rule-like artifacts that read source material and emit evidence. Self-contained folders at `src/efterlev/detectors/`. **The most common and most welcomed contribution type.** Adding a new detector does not require understanding the rest of the codebase.

**Primitives** — typed, MCP-exposed functions that agents call. Smaller surface, more deliberately changed. Adding one is reasonable; changing contracts of existing ones needs discussion first.

**Agents** — reasoning loops that compose primitives. Adding a new agent is a substantial contribution that benefits from a design issue first.

**Output generators** — serializers from our internal model to FRMR (primary, v0), HTML, and (in v1) OSCAL and Word templates. Adding a new output format is welcome; see existing generators as templates.

**Documentation** — always welcome. If something in the docs was confusing or wrong, fix it. If something isn't documented, document it.

**Infrastructure** — test harness, CI, release tooling. Welcome but usually best discussed first.

---

## The one-hour path: adding a detector

This is the contribution shape most likely to get merged same-day. Detectors are self-contained folders at `src/efterlev/detectors/<source>/<capability_name>/`. Each folder contains five files. Here's what goes in each.

Detector IDs are capability-shaped (what the detector checks), not control-numbered. KSIs think in capabilities (e.g., "securing network traffic," "validating resource integrity"), and capability-shaped IDs age better as the KSI ↔ 800-53 mapping in FRMR evolves. Good: `encryption_s3_at_rest`, `tls_alb_listener`, `mfa_iam_policy_condition`. Avoid: `sc_28_s3_encryption`, `ia_2_mfa`.

### 1. `detector.py` — the rule

```python
from datetime import UTC, datetime

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

@detector(
    id="aws.encryption_s3_at_rest",
    ksis=[],                           # DECISIONS 2026-04-21 design call #1 (Option C)
    controls=["SC-28", "SC-28(1)"],    # underlying 800-53 controls
    source="terraform",
    version="0.1.0",
)
def detect(tf_resources: list[TerraformResource]) -> list[Evidence]:
    """
    Detect S3 bucket encryption configuration at rest.

    Evidences (800-53):  SC-28 (Protection at Rest), SC-28(1) (Cryptographic Protection).
    Evidences (KSI):     None — FRMR 0.9.43-beta lists no KSI whose `controls`
                         array contains SC-28. Per DECISIONS 2026-04-21 design
                         call #1 (Option C), we declare ksis=[] rather than
                         fudging a mapping to KSI-SVC-VRI (which is SC-13
                         integrity, different semantic territory). The Gap
                         Agent renders such findings as "unmapped to any
                         current KSI" — the honest representation of the FRMR
                         mapping gap.
    Does NOT prove:      key management practices, rotation, BYOK. Those belong to
                         SC-12 territory and require procedural evidence beyond
                         the infrastructure layer.
    """
    now = datetime.now(UTC)
    evidences: list[Evidence] = []
    for resource in tf_resources:
        if resource.type == "aws_s3_bucket":
            encryption = resource.get_nested("server_side_encryption_configuration")
            # Evidence.create() is the construction path: it computes the
            # content-addressed evidence_id from the record's canonical
            # content. Using Evidence(...) directly would require the caller
            # to pass evidence_id explicitly — fine on deserialization
            # (model_validate), but a bug in normal detector code.
            if encryption:
                evidences.append(Evidence.create(
                    detector_id="aws.encryption_s3_at_rest",
                    ksis_evidenced=[],
                    controls_evidenced=["SC-28", "SC-28(1)"],
                    source_ref=resource.source_ref,
                    content={"resource_name": resource.name, "encryption_state": "present"},
                    timestamp=now,
                ))
            else:
                # Negative evidence — bucket exists without encryption
                evidences.append(Evidence.create(
                    detector_id="aws.encryption_s3_at_rest",
                    ksis_evidenced=[],
                    controls_evidenced=["SC-28"],
                    source_ref=resource.source_ref,
                    content={
                        "resource_name": resource.name,
                        "encryption_state": "absent",
                        "gap": "bucket defined without server_side_encryption_configuration",
                    },
                    timestamp=now,
                ))
    return evidences
```

The "does NOT prove" section of the docstring is **required**. This is how we enforce the evidence-vs-claims discipline at the detector level. When a KSI mapping is uncertain (as with SC-28 under FRMR 0.9.43-beta), name the uncertainty in the docstring and in the detector's README; do not invent a KSI that does not exist in the vendored FRMR.

### 2. `mapping.yaml` — which KSIs and controls

```yaml
detector_id: aws.encryption_s3_at_rest
ksis:
  - id: KSI-SVC-VRI
    theme: KSI-SVC
    evidence_type: infrastructure  # one of: infrastructure, procedural, hybrid
    coverage: partial              # what this detector proves of the KSI
    notes: >
      Nearest thematic fit rather than literal mapping. FRMR 0.9.43-beta does
      not list SC-28 under any KSI's `controls` array; KSI-SVC-VRI is the
      nearest Service-Configuration-theme indicator. Re-evaluate on FRMR GA.
controls:
  - id: SC-28
    enhancements: [SC-28(1)]
    evidence_type: infrastructure
    coverage: partial
    notes: >
      Infrastructure-layer evidence only. Full SC-28 implementation requires
      key management procedures and rotation policies documented elsewhere.
```

### 3. `evidence.yaml` — the schema

```yaml
detector_id: aws.encryption_s3_at_rest
evidence_shape:
  resource: string                 # Terraform resource name
  encryption: object | null        # the encryption configuration block, or null
  gap: string?                     # present only on negative evidence
```

### 4. `fixtures/` — test cases

```
fixtures/
├── should_match/
│   ├── encrypted_bucket.tf
│   └── encrypted_bucket_with_kms.tf
└── should_not_match/
    ├── unencrypted_bucket.tf
    └── no_s3_resources.tf
```

Each `.tf` file in `should_match/` must produce at least one positive evidence record. Each in `should_not_match/` must produce none (or only negative-evidence records in the gap case). The test harness at `tests/detectors/` runs these automatically.

### 5. `README.md` — the human explanation

A short plain-English explanation:
- What this detector checks
- Which KSI(s) it evidences, and which underlying 800-53 control(s)
- What it proves (specifically, which layer of the KSI and control)
- What it does not prove (the other layers, the procedural aspects, known edge cases)
- If the KSI mapping is uncertain or `[TBD]` against the current FRMR, name that explicitly
- Known limitations
- Example output

This file is read by users who want to understand what a finding means. Write it for them, not for the compiler.

### Running the detector tests

```bash
uv run pytest tests/detectors/test_aws_encryption_s3_at_rest.py
```

If your fixtures match what the detector produces, tests pass. If not, the harness tells you what the detector produced and what you expected.

---

## Contribution standards

**Every PR:**
- Passes `ruff` (lint + format) — run `uv run ruff check . && uv run ruff format .`
- Passes `mypy --strict` on touched core paths — run `uv run mypy src/efterlev/primitives src/efterlev/detectors src/efterlev/frmr src/efterlev/oscal`
- Passes `pytest` — run `uv run pytest`
- Has tests for any new detector, primitive, or agent
- Includes a line in `DECISIONS.md` if the change involves a non-trivial choice

**New detectors specifically:**
- Include all five files (detector.py, mapping.yaml, evidence.yaml, fixtures/, README.md)
- Fixtures cover at least one should-match and one should-not-match case
- The detector's docstring includes a "does NOT prove" section
- The `@detector` decorator includes both `ksis=[...]` and `controls=[...]`. KSI IDs must appear verbatim in `catalogs/frmr/FRMR.documentation.json`; if no KSI fits cleanly, mark the mapping decision in the detector's README and open an issue
- Detector ID is capability-shaped (e.g. `aws.encryption_s3_at_rest`), not control-numbered

**New primitives specifically:**
- Typed Pydantic input and output models
- `@primitive` decorator with `capability`, `side_effects`, `version`, and `deterministic` set correctly
- Docstring naming intent, side effects, deterministic/generative classification, external dependencies
- At least one happy-path test and one error-path test
- MCP server auto-registration verified by launching the server (`uv run efterlev mcp serve`) and confirming via an MCP client (e.g. the `scripts/mcp_smoke_client.py` harness) that the new primitive is listed. A standalone `efterlev mcp list` subcommand is not yet implemented — tracked as a follow-up (see `LIMITATIONS.md`).

**New agents specifically:**
- Open a design issue first. Agents are the product's brain; their system prompts deserve review.
- System prompt in a sibling `.md` file, not inlined
- End-to-end test against the demo repo

**Changes to existing contracts:**
- Primitive input/output changes are breaking. Discuss before PR.
- Detector ID changes require a deprecation path.
- Model changes (Evidence, Claim, Provenance) need an architectural issue.

---

## Commit messages

Prefer the form `layer: short imperative description`. Examples:

- `detectors: add aws.tls_alb_listener evidencing KSI-SVC-SNT`
- `primitives: add validate_claim_provenance`
- `agents/gap: tighten the partial-implementation classification prompt`
- `docs: clarify what the encryption_s3_at_rest detector does not prove`
- `ci: add FedRAMP Moderate baseline validation to release workflow`

Bodies are welcome for non-trivial changes. Reference issue numbers with `Refs #123` or `Closes #123`.

---

## Design discussions

Use [GitHub Discussions](https://github.com/lhassa8/efterlev/discussions) for:
- "Should Efterlev support X?" questions
- Proposals for new agents, new output formats, or significant architectural changes
- Questions about how a detector should handle a specific case
- Post-hackathon community coordination

Use GitHub Issues for:
- Bug reports
- Confirmed, scoped feature requests
- Tracked work

When in doubt, start in Discussions. Moving a Discussion to an Issue when the shape is clear is cheap; turning a premature Issue into a Discussion feels bureaucratic.

---

## How maintainer status works

**v0 governance:** benevolent-dictator model. The project author is the sole maintainer and approves all merges.

**Path to committer:** contributors whose PRs consistently show up at the quality bar (described above) and who help triage issues and review others' PRs will be invited to commit rights. There is no formal application — if you've been contributing well for a while, we'll ask.

**At 10 active contributors,** governance moves to a technical steering committee with documented membership criteria. That change is tracked in `DECISIONS.md` and will be discussed publicly when we approach the threshold.

Maintainer responsibilities are light by OSS standards: review PRs, triage issues, keep the main branch green. Maintainer status is not a rank; it's a chore assignment.

---

## Code of conduct

Be respectful. Assume good faith. Disagree technically without being personal.

Specifically for this project:

- **No FUD about competitors.** Our [COMPETITIVE_LANDSCAPE.md](./COMPETITIVE_LANDSCAPE.md) is a model for honest positioning. Comments in issues or PRs that trash Comp AI, RegScale, Vanta, or anyone else will be asked to be reframed.
- **No overclaiming in docs or code.** We are explicit about what Efterlev does not do. Contributions that blur those lines will be asked to tighten their claims. This is not nitpicking; it's the core product discipline.
- **Compliance jargon is okay; gatekeeping is not.** Some contributors will be deep in FedRAMP; others will be strong engineers learning the domain. If someone asks a basic compliance question, explain it. The domain needs more people in it, not fewer.

A formal Code of Conduct based on the [Contributor Covenant](https://www.contributor-covenant.org/) will be added before v1 release.

---

## Reporting security issues

Do **not** file security issues as public GitHub issues.

See [SECURITY.md](./SECURITY.md) for the coordinated disclosure process. (Until SECURITY.md exists, email the maintainer directly.)

---

## License of contributions

By contributing, you agree your contributions are licensed under the project's Apache 2.0 license. A Contributor License Agreement may be introduced at v1 if the project is donated to a foundation; contributors will be notified and asked to consent before that change.

---

## Questions this document didn't answer

Open a [Discussion](https://github.com/lhassa8/efterlev/discussions). If enough people ask the same question, it lands in this document.

Welcome. We're glad you're here.
