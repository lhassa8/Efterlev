# Efterlev

**Compliance automation for SaaS companies pursuing their first FedRAMP Moderate authorization via the FedRAMP 20x pilot.**

Scans your Terraform for KSI-level evidence. Drafts FRMR-compatible validation data for your 3PAO. Proposes code-level remediations you can apply today. Runs locally — no SaaS, no telemetry, no procurement cycle.

[:material-rocket-launch: Get started](quickstart.md){ .md-button .md-button--primary }
[:material-book-open: Read the concepts](concepts/ksis-for-engineers.md){ .md-button }
[:material-github: View on GitHub](https://github.com/efterlev/efterlev){ .md-button }

```bash
pipx install efterlev
cd path/to/your-repo
efterlev init --baseline fedramp-20x-moderate
efterlev scan
```

Pronounced "EF-ter-lev." From Swedish *efterlevnad* (compliance).

---

## What it does

- **Scans** Terraform source for evidence of FedRAMP 20x Key Security Indicators (KSIs), backed by NIST 800-53 Rev 5 controls.
- **Drafts** FRMR-compatible attestation JSON grounded in that evidence, with every assertion citing its source line.
- **Proposes** code-level remediation diffs for detected gaps.
- **Emits** machine-readable validation data ready for 3PAO review and the FedRAMP 20x automated validation pipeline.
- **Traces** every generated claim back to the source line that produced it.

Everything runs locally. The only outbound network call is to your configured LLM endpoint (Anthropic direct or AWS Bedrock for GovCloud) for reasoning tasks. Scanner output is deterministic and offline.

## What it doesn't do

- It does not produce an Authorization to Operate. Humans and 3PAOs do that.
- It does not certify compliance. It produces drafts that accelerate the human review cycle.
- It does not guarantee generated narratives are correct. Every LLM-generated artifact is marked `DRAFT — requires human review`.
- It does not cover SOC 2, ISO 27001, HIPAA, or GDPR. Other tools serve those well; see [comparisons](comparisons/comp-ai.md).
- It does not scan live cloud infrastructure yet. v1.5+.

[Full accounting in LIMITATIONS.md](https://github.com/efterlev/efterlev/blob/main/LIMITATIONS.md)

---

## Why Efterlev

A 100-person SaaS company just got told by its biggest prospect: *"we'll buy, but only if you're FedRAMP Moderate by next year."*

The team looks at each other. Nobody's done this before. They google it and find:

- Consulting engagements starting at $250K
- SaaS compliance platforms that cover SOC 2 beautifully but treat FedRAMP as a footnote
- Enterprise GRC tooling priced for the wrong scale
- Spreadsheets, Word templates, and a NIST document family that runs to thousands of pages

What they actually need is something that reads their Terraform and tells them, in their own language, what's wrong and how to fix it. Something a single engineer can install on a Tuesday and show results at Wednesday's standup. Something whose output is concrete enough that their 3PAO can use it — and whose claims are honest enough that the 3PAO won't throw it out.

Efterlev is that tool.

[Read the full ICP](https://github.com/efterlev/efterlev/blob/main/docs/icp.md)

---

## How it's built

Three layers, each with a clear job.

- **Detectors** — small deterministic Python rules that read Terraform and emit evidence. 30 ship at v0.1.0; the long-term plan is hundreds, contributed by the community.
- **Primitives** — typed functions that wrap the things agents need to do: load a catalog, validate output, render a report. Stable interface layer.
- **Agents** — reasoning loops that compose primitives. Three at v0.1.0: Gap (classify each KSI), Documentation (draft FRMR attestations), Remediation (propose code-level fixes).

[Read the architecture overview](architecture.md)

---

## Status

- **v0.1.0 released:** PyPI + container + GitHub Action + AWS GovCloud Bedrock backend + 31 detectors + full provenance graph.
- **Open source:** Apache 2.0. Pure OSS — no commercial tier, no paid layer, no managed SaaS, ever. [Why](https://github.com/efterlev/efterlev/blob/main/DECISIONS.md).
- **Governance:** BDFL today, technical steering committee at 10 sustained contributors. [Details](https://github.com/efterlev/efterlev/blob/main/GOVERNANCE.md).

---

*Efterlev is built for the VP Eng or DevSecOps lead whose CEO just said "we need FedRAMP" and who needs to know, by Monday, where they actually stand.*
