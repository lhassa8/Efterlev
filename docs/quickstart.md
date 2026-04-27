# Quickstart

> Five minutes from zero to your first scan finding.

## What you'll do

1. Install Efterlev.
2. Initialize a workspace in a sample Terraform repo.
3. Run `efterlev scan` and see findings.
4. (Optional) Run the Gap Agent for an LLM-classified report.

What you won't need: an account, a credit card, a SaaS dashboard, or a procurement approval. Efterlev runs locally on your machine.

## Prerequisites

- Python 3.12 or later. Check with `python3 --version`.
- A Terraform repository to scan against. If you don't have one handy, clone the demo repo we use throughout this guide:

    ```bash
    git clone https://github.com/efterlev/govnotes-demo.git
    cd govnotes-demo
    ```

## 1. Install

=== "pipx (recommended)"

    `pipx` keeps Efterlev isolated from your system Python while giving you a globally-callable `efterlev` CLI.

    ```bash
    pipx install efterlev
    efterlev --version
    ```

=== "uv"

    ```bash
    uv tool install efterlev
    efterlev --version
    ```

=== "Container"

    No install needed; the container ships with everything baked in.

    ```bash
    docker pull ghcr.io/efterlev/efterlev:latest
    docker run --rm ghcr.io/efterlev/efterlev:latest --version
    ```

    For container-based scans, prefix every command in this guide with:

    ```bash
    docker run --rm -v $(pwd):/repo -w /repo ghcr.io/efterlev/efterlev:latest
    ```

[Full per-platform install instructions →](tutorials/install.md)

## 2. Initialize the workspace

```bash
efterlev init --baseline fedramp-20x-moderate
```

This creates a `.efterlev/` directory with:

- The vendored FedRAMP FRMR catalog.
- The vendored NIST 800-53 Rev 5 catalog.
- A SQLite-backed provenance store.
- A `config.toml` recording the baseline + LLM backend choices.

Output:

```
Initialized .efterlev/
  baseline:              fedramp-20x-moderate
  FRMR:                  v0.9.43-beta (2026-04-08, 11 themes, 60 indicators)
  NIST SP 800-53 Rev 5:  324 controls (+872 enhancements)
  load receipt:          sha256:4dad52a9...
```

## 3. Scan

```bash
efterlev scan
```

This runs 30 deterministic detectors against your Terraform. No LLM calls, no network — pure local rules over your `.tf` files.

Expected output for the govnotes demo:

```
Scanning .
  ✓ aws.encryption_s3_at_rest        — 4 evidence records
  ✓ aws.tls_on_lb_listeners          — 1 evidence record
  ✓ aws.security_group_open_ingress  — 2 findings
  ...
41 detectors run, 67 evidence records, 14 findings.
HTML report: .efterlev/reports/scan-20260425T140530Z.html
```

Open the HTML report in your browser:

```bash
open .efterlev/reports/scan-*.html  # macOS
xdg-open .efterlev/reports/scan-*.html  # Linux
```

You'll see every finding with the `.tf` file and line number that produced it. Click any finding to walk back through the provenance chain.

## 4. (Optional) Run the Gap Agent

The Gap Agent uses Claude to classify each KSI as `implemented` / `partial` / `not_implemented` / `not_applicable` / `evidence_layer_inapplicable`, grounded in the scanner's evidence. The fifth status (SPEC-57.1) is for KSIs the scanner cannot evidence from infrastructure-as-code by design — procedural commitments like the FedRAMP Security Inbox — distinct from KSIs the CSP doesn't implement. This is the LLM step — it requires an API key.

=== "Anthropic API"

    ```bash
    export ANTHROPIC_API_KEY="sk-ant-..."
    efterlev agent gap
    ```

=== "AWS Bedrock"

    First reconfigure your workspace to use Bedrock:

    ```bash
    efterlev init --force \
      --baseline fedramp-20x-moderate \
      --llm-backend bedrock \
      --llm-region us-east-1 \
      --llm-model us.anthropic.claude-opus-4-7-v1:0
    ```

    Then ensure AWS credentials are available (`aws configure list` or via instance profile). The Bedrock backend uses your existing AWS auth.

    ```bash
    efterlev agent gap
    ```

    For GovCloud, [follow the GovCloud deploy tutorial →](tutorials/deploy-govcloud-ec2.md)

The Gap Agent produces a second HTML report with each KSI classified and explained, every claim citing the underlying evidence by content-addressed ID.

```
Gap Agent: classified 60 KSIs in 47 seconds.
HTML report: .efterlev/reports/gap-20260425T140617Z.html
Cost: $1.24 (claude-opus-4-7 via anthropic-direct)
```

Every claim carries a `DRAFT — requires human review` marker. The agent never claims authorization.

## What's next

- [Drafting attestations →](https://github.com/efterlev/efterlev/blob/main/docs/icp.md) — the Documentation Agent turns gap classifications into FRMR-compatible JSON.
- [Proposing remediations →](tutorials/write-a-detector.md) — the Remediation Agent generates Terraform diffs for findings.
- [Wire it into CI →](tutorials/ci-github-actions.md) — three lines of YAML and every PR shows a compliance delta.
- [Run inside a GovCloud boundary →](tutorials/deploy-govcloud-ec2.md) — the Bedrock backend keeps inference inside the FedRAMP-authorized boundary.

## Troubleshooting

**`efterlev: command not found`** after `pipx install` — make sure `~/.local/bin` is on your PATH. `pipx ensurepath` adds it.

**`anthropic completion failed: 401`** — your `ANTHROPIC_API_KEY` is invalid or unset. Re-export and try again.

**Init fails with `baseline ... is not supported`** — v0.1.0 supports `fedramp-20x-moderate` only. Other baselines land as customer demand surfaces.

**Scan finds zero evidence** — your detectors may not match your stack (we ship 30 AWS-Terraform detectors at v0.1.0; non-AWS stacks see less). [Check the detector reference](reference/detectors.md) for what's covered.

Anything else: [open an issue](https://github.com/efterlev/efterlev/issues/new/choose) — broken first-runs are bugs we want to hear about.
