# Manual verification runbook

A generic template for walking a deployment mode end-to-end. Used when CI can't cover the mode (e.g., GovCloud EC2, Jenkins, air-gap) or when extra confirmation is wanted before a release.

The output of a walkthrough is a single PR: an updated row in [`deployment-modes.md`](deployment-modes.md) graduating ⚪ → 🟡. That's the durable record. This runbook is the procedure that produces it.

## Pre-flight

Before starting:

- **Target environment.** Pick exactly one mode from `deployment-modes.md`. Walking two modes in one runbook conflates failure attribution.
- **Throwaway instance.** Use a fresh VM, container, or CI project. Never walk a runbook on production state — verifying a production deploy isn't the same exercise.
- **Account credentials.** AWS account (commercial or GovCloud), CI provider account (GitLab/CircleCI/Jenkins admin), Anthropic API key — whichever the mode requires.
- **Notebook.** Keep notes; surprises become matrix-doc footnotes.

## Setup

1. Provision the target environment per its tutorial (`docs/tutorials/<mode>.md`).
2. Capture the host fingerprint: OS + kernel + arch + container-runtime version (if applicable). Pasted into the verification record.
3. Install Efterlev per the tutorial. Capture the install command and output.

## Smoke test

The minimum viable check, identical across all modes:

```bash
# Inside the target environment, in any directory:
efterlev --version
efterlev init --baseline fedramp-20x-moderate
efterlev scan
ls .efterlev/reports/
```

Container variant:

```bash
docker run --rm ghcr.io/efterlev/efterlev:<version> --version
docker run --rm -v $(pwd):/repo -w /repo ghcr.io/efterlev/efterlev:<version> init --baseline fedramp-20x-moderate
docker run --rm -v $(pwd):/repo -w /repo ghcr.io/efterlev/efterlev:<version> scan
ls .efterlev/reports/
```

For modes with an LLM backend (GovCloud Bedrock, AWS-EC2 + Bedrock, etc.) optionally extend with the agent step:

```bash
efterlev agent gap
```

## Pass criteria

All of:

- `efterlev --version` exits 0 and prints the expected version string.
- `efterlev init` creates `.efterlev/` and writes `config.toml` with the expected backend.
- `efterlev scan` exits 0 and produces at least one HTML report under `.efterlev/reports/`.
- `efterlev scan` runs the expected detector count (`grep -c "✓ aws\." <stdout>` ≥ 30 for v0.1.0+; the exact count depends on your fixture).
- (If exercising agents) `efterlev agent gap` exits 0; report HTML present; `cat .efterlev/redactions/*.jsonl | wc -l` matches expected redactions for the prompt's input.

## Cleanup

Leave-no-trace teardown:

- Tear down the throwaway VM / CI project / EC2 instance.
- Revoke any temporary credentials issued for the walkthrough.
- Delete the `.efterlev/` directory if the walkthrough was on a host you'll keep.

## Record

Open a PR that updates [`deployment-modes.md`](deployment-modes.md):

- Change the mode's status icon ⚪ → 🟡.
- Update the "Latest" column with `<commit-sha> @ <YYYY-MM-DD> (reviewed by @<your-handle>)`.
- Add a "Notes" column entry for any surprises: OS-specific gotchas, environmental setup steps not in the tutorial, performance observations.

If the walkthrough **failed**, open an issue first naming exactly what broke; the matrix entry stays ⚪ until a follow-up PR lands the fix and the runbook re-passes. Failed walkthroughs are valuable data — file them publicly.

## Optional: PR template snippet

Copy into your PR description:

```markdown
## Manual-verification record: <mode name>

- Target environment: <OS + arch + extras>
- Efterlev version: <X.Y.Z>
- Commit SHA: <full SHA>
- Walked at: <YYYY-MM-DD>
- Reviewer: @<handle>

### Pass criteria

- [ ] `efterlev --version` exits 0 with expected version
- [ ] `efterlev init` creates `.efterlev/` correctly
- [ ] `efterlev scan` produces an HTML report
- [ ] Detector count matches expectation (≥30 for v0.1.0+)
- [ ] (If agents exercised) `efterlev agent gap` produces a report

### Surprises

<bullet list of anything not already in the tutorial>

### Matrix update

See `docs/deployment-modes.md` diff.
```
