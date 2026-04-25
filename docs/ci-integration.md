# CI integration — GitHub Actions

Efterlev ships a PR-level compliance-scan workflow at
`.github/workflows/pr-compliance-scan.yml`. This page documents how to
adapt it for a consuming repo (your Terraform-holding SaaS repo) once
Efterlev is installable.

The workflow runs on any PR that touches `.tf`, `.tfvars`, or
`.efterlev/manifests/` files. It scans the PR's infrastructure,
surfaces findings as a sticky PR comment (one comment per PR, updated
in-place on new commits), and uploads the full HTML/markdown reports
as a workflow artifact for deeper review.

## What the workflow does

1. **Checkout.** Checks out the PR head.
2. **Install Efterlev.** Today: `uv sync --extra dev` (clone-and-install
   against the private repo). Post-v1 public release: `pipx install
   efterlev`.
3. **Init workspace.** `efterlev init --baseline fedramp-20x-moderate
   --force` — `--force` because the workspace must be rebuilt fresh
   on each run.
4. **Scan.** `efterlev scan` — runs every registered detector against
   the repo's `.tf` files. Deterministic, no LLM call.
5. **Gap Agent (optional).** If `ANTHROPIC_API_KEY` is available as a
   secret, runs `efterlev agent gap` to produce KSI-level
   classifications. Failure here logs a warning and proceeds with the
   scanner-only summary; it does NOT fail the workflow.
6. **Format comment.** `python scripts/ci_pr_summary.py` renders the
   findings + coverage + (if present) KSI classifications as
   markdown.
7. **Post or update PR comment.** Finds a prior Efterlev comment (by
   the `## 🧪 Efterlev compliance scan` header) and edits it in place;
   otherwise creates a new one.
8. **Upload artifact.** The `.efterlev/reports/` directory (HTML gap
   report, FRMR attestation JSON, POA&M markdown, remediation HTML if
   generated) uploads as `efterlev-reports-<run-id>` for 14-day
   retention.

## Drop it into your repo

Two files, no other changes:

1. **`.github/workflows/pr-compliance-scan.yml`** — copy verbatim from
   Efterlev's repo. Change the `Install Efterlev` step per the
   comments in the file.
2. **`.github/workflows/efterlev-helper` or equivalent.** If you use
   the scripted `ci_pr_summary.py` path, vendor it or let the
   workflow install it from Efterlev.

## Enabling the Gap Agent

To include KSI-level classifications in the PR comment:

1. **Repo settings → Secrets and variables → Actions → New repository
   secret.**
2. Name: `ANTHROPIC_API_KEY`, Value: your Anthropic API key.
3. The workflow auto-detects the secret. No other config needed.

Budget note: a full Gap run is ~88 seconds of Opus time per PR (one
60-KSI classification call). If your repo has frequent PRs or you
want to skip agent runs on small PRs, add a condition to the
`Run Gap Agent` step.

## Secret redaction (built-in)

Every prompt that would go to the LLM passes through
`src/efterlev/llm/scrubber.py` before transmission. Structural
secrets (AWS keys, GitHub tokens, PEM private keys, etc.) are
replaced with `[REDACTED:<kind>:sha256:<8hex>]` tokens. The redaction
audit trail lands in `.efterlev/redacted.log` inside the workflow
runner (uploaded as part of the reports artifact).

See `THREAT_MODEL.md` "Secrets handling" for the full pattern library
and limitations.

## Failing the PR on findings

By default the workflow posts findings as a comment without failing
the PR check — surfacing is the primary value; gating is a policy
call each org makes differently.

To fail the PR when any gap-shaped evidence appears, change the
`Format PR comment` step to pass `--fail-on-finding`:

```yaml
- name: Format PR comment
  run: |
    uv run python scripts/ci_pr_summary.py \
      --efterlev-dir "${{ steps.target.outputs.target }}/.efterlev" \
      --output /tmp/efterlev-pr-comment.md \
      --fail-on-finding
```

The comment still posts (captured in the next step); the workflow
fails only if findings are present.

## Regression detection (v2 roadmap)

The current workflow surfaces all findings on every PR. A future
version will diff against the base branch and flag only NEW findings
— true regression detection. Requires scanning both branches and
diffing evidence content. Tracked as a follow-up.

## What doesn't work yet

- **PyPI release.** Today Efterlev installs from a cloned checkout;
  PyPI release lands as part of pre-launch readiness gate A2 and
  coincides with the public-repo flip. See `DECISIONS.md` 2026-04-23
  "Rescind closed-source lock."
- **Composite action / marketplace listing.** The workflow is
  drop-in today; a reusable `uses: efterlev/scan-action@v1` form
  lands alongside the PyPI package at launch.
- **Line-level PR annotations.** Current output is a single sticky
  comment with findings in a table. GitHub's "review annotations"
  API would surface each finding as a line comment on the
  offending `.tf` file; that's a follow-up.

## What the workflow does NOT send to your LLM provider

Without `ANTHROPIC_API_KEY` set, Efterlev makes no LLM calls at all.
The scanner runs deterministically against your `.tf` files, produces
evidence records locally, and the PR comment is rendered entirely
from local data. Scanner-only mode is the right default for
sensitive codebases.

With the key set, the Gap Agent sends evidence content (post-
redaction) to Anthropic. The redaction pass runs unconditionally;
even if a detector emits unexpected content, the scrubber catches
structural secrets before transmission. See `THREAT_MODEL.md` for
the complete trust model.
