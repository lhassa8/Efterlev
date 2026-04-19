# v0 MVP Scope

This document is the single source of truth for what Efterlev does and does not do at v0. If it contradicts another document on an MVP scope question, this document wins. Roadmap and v1 questions belong to [`docs/dual_horizon_plan.md`](./dual_horizon_plan.md).

## What v0 is

A 4-day hackathon build of a repo-native, KSI-native compliance scanner. A user clones the repo, runs `efterlev scan` against the demo target (govnotes), gets deterministic findings with full provenance, then drives three agents — Gap, Documentation, Remediation — to produce a KSI status report, an FRMR-compatible attestation draft, and a code-level remediation diff. A second Claude Code session connects to Efterlev's MCP server and calls a primitive directly. That second session is the architectural proof moment, and the whole demo above is what v0 ships.

## In scope (v0)

### Detection

| Area | KSI | 800-53 | Signal source |
|---|---|---|---|
| Encryption at rest | `[TBD]` — closest fit KSI-SVC-VRI | SC-28, SC-28(1) | Terraform S3/RDS/EBS |
| Transmission confidentiality | KSI-SVC-SNT | SC-8 | Terraform ALB/TLS |
| Cryptographic protection | KSI-SVC-VRI | SC-13 | Terraform, source |
| MFA enforcement | KSI-IAM-MFA | IA-2 | Terraform IAM policy conditions |
| Event logging & audit generation | KSI-MLA-LET, KSI-MLA-OSM | AU-2, AU-12 | Terraform CloudTrail |
| System backup | KSI-RPL-ABO | CP-9 | Terraform RDS/S3 versioning |

### Agents

| Agent | Artifact | Primary job |
|---|---|---|
| Gap | `GapReport` | Classifies KSI status (implemented / partial / not / compensating / NA) |
| Documentation | `AttestationDraft` → FRMR JSON + HTML | Drafts FRMR attestation grounded in evidence |
| Remediation | Code diff | Proposes a Terraform change for a selected finding |

### Inputs, outputs, surface

| Dimension | v0 |
|---|---|
| Input source | Terraform and OpenTofu (`.tf`) |
| Target cloud | AWS |
| Primary output | FRMR-compatible JSON validated against the vendored schema |
| Secondary outputs | HTML reports, Markdown summaries |
| Input catalogs | FRMR (`FedRAMP/docs`) and NIST SP 800-53 Rev 5 (`usnistgov/oscal-content`); both vendored in `catalogs/` |
| Runtime | Local CLI only; no SaaS, no server mode except the stdio MCP server |
| State | `.efterlev/` in the working directory (SQLite + content-addressed blob store) |
| Agent interface | MCP stdio (`efterlev mcp serve`); external Claude Code sessions can discover and call every primitive |
| Provenance | Append-only, content-addressed, versioned; `efterlev provenance show <id>` walks the chain |
| Demo target | `demo/govnotes/` — a synthetic gov-adjacent SaaS with deliberate gaps the agents exercise. Will be added as a git submodule pinned to a specific commit once the upstream repo is initialized; until then, `demo/` is an empty placeholder. |

## Out of scope for v0 (deferred to v1 or later)

| Deferred to | Item |
|---|---|
| v1 (month 1) | OSCAL output generators (Assessment Results, partial SSP, POA&M) for Rev5 transition users |
| v1 (month 1) | Terraform Plan JSON support (resolved-plan scanning) |
| v1 (month 2) | CloudFormation and AWS CDK input |
| v1 (month 3) | Kubernetes manifests and Helm input |
| v1 (month 4) | Pulumi input; GitHub Action / CI integration with PR comments |
| v1 (month 5) | CMMC 2.0 overlay |
| v1 (month 6) | Drift Agent / continuous monitoring |
| v1.5+ | DoD Impact Levels (IL4/5/6); CUI handling; air-gap deployment mode |
| v1.5+ | Runtime cloud API scanning |
| v2+ | Multi-repo coordination; organization-scoped policy packs |
| Not planned | SOC 2, ISO 27001, HIPAA, PCI-DSS, GDPR — other tools serve those well |
| Not planned | Web UI beyond statically rendered HTML reports |
| Not planned | Authentication, multi-tenancy, hosted deployment |
| Not planned | Real PR creation against remote repos (v0 demo shows local diffs only) |

See [`docs/dual_horizon_plan.md`](./dual_horizon_plan.md) §3 for the full v1 roadmap and the reasoning behind the month-by-month sequencing.

## Never in scope

Three items are out permanently, regardless of version, because keeping them out is part of what Efterlev is:

- **Claiming to produce an ATO, a pass, or a guarantee of compliance.** Efterlev produces drafts and findings. Authorization decisions are human and governmental.
- **Removing the "DRAFT — requires human review" marker from Claims.** LLM-generated output is flagged, always, no exceptions, no `--i-know-what-im-doing` flag.
- **Telemetry, analytics, or phone-home behavior.** The only outbound network calls Efterlev ever makes are to the user's configured LLM endpoint and to vendored-catalog update URLs on explicit user action. Secrets detected during scanning are hashed before any logging. See [`THREAT_MODEL.md`](../THREAT_MODEL.md) for the full security posture.

## Related documents

- [`docs/dual_horizon_plan.md`](./dual_horizon_plan.md) — the 4-day hackathon plan and the 3–6 month v1 roadmap
- [`docs/architecture.md`](./architecture.md) — how the system is organized (detectors, primitives, agents, provenance)
- [`LIMITATIONS.md`](../LIMITATIONS.md) — honest accounting of what Efterlev does and does not do inside scope
- [`DECISIONS.md`](../DECISIONS.md) — append-only record of why scope is what it is
