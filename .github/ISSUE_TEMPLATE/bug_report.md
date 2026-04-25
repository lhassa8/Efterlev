---
name: Bug report
about: Something Efterlev did that it shouldn't have, or didn't do that it should have.
title: ""
labels: ["bug"]
assignees: []
---

## What happened

A clear, concise description of what's wrong.

## Reproduction

1. Step 1...
2. Step 2...
3. Observed: <what you saw>
4. Expected: <what you expected>

If you can include a minimal Terraform fixture that reproduces it, even better.

## Environment

- Efterlev version: (`efterlev --version`)
- Install method: (pipx / uv / container / from source)
- OS + arch: (macOS arm64 / Ubuntu 22.04 x86_64 / Windows 2022 / etc.)
- Python version: (`python3 --version` — only relevant for pipx / uv installs)
- LLM backend: (anthropic-direct / Bedrock commercial / Bedrock GovCloud)

## Scan-store snippet (if relevant)

If the bug involves the provenance store, attach:

- The relevant evidence record (`efterlev provenance show <id>`)
- Sanitize anything sensitive — the secret redaction in the LLM prompt path doesn't run on store records you copy-paste into an issue.

## Anything else

Logs, screenshots, hunches.
