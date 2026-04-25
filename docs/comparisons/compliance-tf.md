# Efterlev vs compliance.tf

compliance.tf is a Terraform-compliance enforcement tool. It enforces 185 FedRAMP Moderate Rev 4 controls automatically by replacing user-authored modules with compliant module versions at registry-download time. Q2 2026 added scan/edit/enforce custom rules.

Stub for SPEC-38.12. Substantial content lands in a follow-up batch. The short version:

- **compliance.tf is prevention-model:** non-compliant infrastructure can't be deployed. Powerful for greenfield Terraform; less applicable to an existing codebase you don't want to rewrite.
- **Efterlev is detection-then-remediation-with-human-review:** scans your existing Terraform, surfaces findings, proposes diffs. Works against any state of codebase.
- **Coexistence is reasonable.** A team can run compliance.tf at module-download time AND Efterlev at scan time; they cover overlapping but distinct surfaces.

[Source: COMPETITIVE_LANDSCAPE.md →](https://github.com/efterlev/efterlev/blob/main/COMPETITIVE_LANDSCAPE.md)
