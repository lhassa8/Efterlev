# CI integration: GitHub Actions

Three lines of YAML and every PR shows a compliance delta.

## Quick start

Add to `.github/workflows/compliance.yml` in your Terraform repo:

```yaml
name: Compliance scan

on:
  pull_request:
    paths:
      - '**/*.tf'
      - '**/*.tfvars'
      - '.efterlev/manifests/**'

jobs:
  efterlev-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v5
      - uses: efterlev/scan-action@v1
```

That's it. On every PR that touches Terraform, the action installs Efterlev, runs the scanner, and posts a sticky comment summarizing findings. The comment updates in place across re-runs — it doesn't duplicate.

## With the Gap Agent (optional)

The Gap Agent uses Claude to classify each KSI's posture. Opt in:

```yaml
- uses: efterlev/scan-action@v1
  with:
    run-gap-agent: true
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

If `ANTHROPIC_API_KEY` is unset, the agent step is skipped with a warning; the scan still runs.

## All inputs

| Input | Default | Description |
|---|---|---|
| `target-dir` | `.` | Directory to scan, relative to the workspace |
| `baseline` | `fedramp-20x-moderate` | FRMR baseline name |
| `efterlev-version` | `latest` | Specific version (e.g. `0.1.0`) or `latest` |
| `run-gap-agent` | `false` | Run the Gap Agent (requires `ANTHROPIC_API_KEY`) |
| `fail-on-finding` | `false` | Exit non-zero if any finding is detected |
| `comment-on-pr` | `true` | Post a sticky PR comment (only on pull_request events) |
| `install-method` | `pipx` | `pipx` or `container` |

## Gating merges on findings

```yaml
- uses: efterlev/scan-action@v1
  with:
    fail-on-finding: true
```

Use sparingly. Efterlev's detectors are deliberately partial — gating on any finding before the detector library is matched to your stack risks false-positive blocks. Most teams start with `fail-on-finding: false` plus the sticky comment, then tighten as the detector set stabilizes against their infra.

## What the action does NOT do

- Modify your code (the Remediation Agent's `--open-pr` flag is post-launch C2; not in v1.0.0 of the action).
- Send your Terraform to anyone (scanner is local; only the agent step calls Claude, with secret redaction).
- Detect drift (the Drift Agent is post-launch C1).

[scan-action source →](https://github.com/efterlev/scan-action)
