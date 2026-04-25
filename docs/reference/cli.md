# CLI reference

Stub for SPEC-38.13. Auto-generation from Typer command help is queued for a follow-up batch.

For the current authoritative reference, run `efterlev --help` and `efterlev <subcommand> --help` for each subcommand:

- `efterlev init` — scaffold `.efterlev/`, load catalogs, write config.
- `efterlev scan` — run all detectors against the target Terraform.
- `efterlev agent gap` — classify each KSI's posture.
- `efterlev agent document` — draft FRMR-compatible attestation JSON.
- `efterlev agent remediate --ksi KSI-X` — propose a remediation diff for a finding.
- `efterlev provenance show <record_id>` — walk the provenance chain.
- `efterlev mcp serve` — expose primitives over MCP stdio.
- `efterlev poam` — emit a Plan of Action & Milestones markdown.
- `efterlev redaction review` — audit the LLM-prompt redaction log.
