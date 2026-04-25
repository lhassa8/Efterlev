# Contributing to Efterlev

> **Status (2026-04-23): pre-launch; external contributions will open the moment the repo flips public.** Efterlev is in the final readiness gates before its public open-source launch; the repo is staged private during that window but the open-source-first commitment is locked (see `DECISIONS.md` 2026-04-23 "Rescind closed-source lock"). Once the eight pre-launch readiness gates pass (A1 identity/governance through A8 launch rehearsal), the repo goes public and this document becomes the canonical contribution path. The contribution flow described below — detectors as the most-welcomed type, the five-file detector contract, the standards checklist — is authoritative starting from launch day. Prospective contributors watching the repo: the signal to start is the public-visibility flip; at that point `good first issue` tickets will already be open.

We want contributors. This document is the path from curiosity to merged PR. It is written for a human developer, not for Claude Code — that's what `CLAUDE.md` is for.

---

## The short version

- Five-minute path: clone, install, run tests, see them pass.
- One-hour path: pick an issue labeled `good first issue`, add a detector or fix a bug, open a PR with a passing test.
- Most valuable contribution type right now: new detectors for FedRAMP Moderate controls on the roadmap.
- Questions? Open a [GitHub Discussion](https://github.com/efterlev/efterlev/discussions) before writing much code.

---

## Five-minute path: get a working environment

```bash
# Clone
git clone https://github.com/efterlev/efterlev.git
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
- **Every commit is DCO-signed-off** — use `git commit -s` so each commit message carries a `Signed-off-by:` trailer. Branch protection on `main` blocks merges without DCO sign-off. See the "Signing and DCO sign-off" section below for details.

**Signing and DCO sign-off:**

- **All commits** (contributors and maintainers) must include a `Signed-off-by: Full Name <email>` trailer. Use `git commit -s` to add it automatically; `git commit -s --amend` to fix a missed one. By signing off you certify the Developer Certificate of Origin ([developercertificate.org](https://developercertificate.org)) — essentially a promise that you have the right to contribute the work under the project's Apache 2.0 license.
- **Maintainer commits** must additionally be SSH-signed. Configure git to sign with Ed25519 SSH:
  ```bash
  git config --global user.signingkey ~/.ssh/your_signing_key.pub
  git config --global gpg.format ssh
  git config --global commit.gpgsign true
  git config --global tag.gpgsign true
  ```
  Register the public half on your GitHub profile as a Signing Key and add a record to [`.github/SIGNING_KEYS.md`](./.github/SIGNING_KEYS.md) in your onboarding PR.
- **Contributors are encouraged but not required to sign.** Signing is optional for non-maintainer PRs to keep the first-contribution barrier low; DCO sign-off is the hard requirement.
- **Default merge strategy is squash-and-merge.** The squash commit is signed by the merging maintainer and preserves the contributor's DCO sign-off from the merged commits in the squash-commit body. Contributors never lose their attribution or sign-off.

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

Use [GitHub Discussions](https://github.com/efterlev/efterlev/discussions) for:
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

The full picture lives in [GOVERNANCE.md](./GOVERNANCE.md). Summary:

- **Today:** benevolent-dictator model. The BDFL (`@lhassa8`) is the sole maintainer and approves all merges.
- **Path to maintainer:** no application. Contributors whose PRs show up consistently at the quality bar — lint/type/test clean, evidence-vs-claims discipline upheld, detector READMEs honest about what they don't prove — and who participate thoughtfully in others' reviews will be invited to join the merge team. Rough bar: ~10+ merged PRs over 3+ months, with demonstrated judgment on ambiguous calls.
- **At 10 sustained active contributors** (at least one merged PR in each of the prior 3 calendar months, sustained for 6 months), governance transitions to a technical steering committee via a public `DECISIONS.md` entry and a 30-day comment window.

Maintainer responsibilities are light by OSS standards: review PRs, triage issues, keep `main` green. Maintainer status is not a rank; it's a chore assignment.

---

## Code of conduct

Efterlev adopts the [Contributor Covenant 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) as its Code of Conduct. Full text, enforcement contact, response-time commitment, and the Efterlev-specific interpretation section live in [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md). Enforcement contact: `conduct@efterlev.com`.

The project-specific interpretation (detailed in `CODE_OF_CONDUCT.md`) codifies three norms that apply to contributions in this repo:

- **No FUD about competitors.** Our [COMPETITIVE_LANDSCAPE.md](./COMPETITIVE_LANDSCAPE.md) is the model for honest positioning. Comments in issues or PRs that disparage Paramify, compliance.tf, Comp AI, RegScale, Vanta, or anyone else will be asked to be reframed.
- **No overclaiming in docs or code.** We are explicit about what Efterlev does not do. Contributions that blur those lines will be asked to tighten their claims. This is not nitpicking; it's the core product discipline.
- **Compliance jargon is okay; gatekeeping is not.** Some contributors will be deep in FedRAMP; others will be strong engineers learning the domain. If someone asks a basic compliance question, explain it. The domain needs more people in it, not fewer.

---

## Reporting security issues

Do **not** file security issues as public GitHub issues.

See [SECURITY.md](./SECURITY.md) for the coordinated disclosure process. (Until SECURITY.md exists, email the maintainer directly.)

---

## License of contributions

By contributing, you agree your contributions are licensed under the project's Apache 2.0 license. Efterlev uses the Developer Certificate of Origin (DCO) rather than a CLA — no legal paperwork, no copyright assignment. The per-commit `git commit -s` sign-off is the certification; see the "Signing and DCO sign-off" section above for the full flow and the rationale. If the project is ever donated to a foundation (OpenSSF / LF / CNCF), contributors will be notified and asked to consent before any licensing change.

---

## Questions this document didn't answer

Open a [Discussion](https://github.com/efterlev/efterlev/discussions). If enough people ask the same question, it lands in this document.

Welcome. We're glad you're here.
