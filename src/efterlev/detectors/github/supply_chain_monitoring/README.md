# github.supply_chain_monitoring

Detects whether `.github/workflows/*.yml` workflows include automated
SBOM-generation or upstream-vulnerability-scanning tooling. KSI-SCR-MON
("Monitoring Supply Chain Risk") asks the customer to *automatically
monitor third-party software information resources for upstream
vulnerabilities*; a CI workflow running `syft` + `grype` (or any
equivalent SBOM + scanner pair) is the canonical IaC-evidenceable signal.

This is the second detector in the `github-workflows` source category,
sibling to `github.ci_validation_gates`.

## What it proves

- **RA-5 (Vulnerability Monitoring and Scanning)** — a workflow runs
  one or more known SBOM or CVE-scanning tools in CI. The customer is
  performing automated supply-chain monitoring rather than relying on
  manual review.

## What it does NOT prove

- **That the scan step fails the build on a finding.** Some workflows
  run `trivy fs` but proceed regardless of its exit code. We detect
  presence of the step, not failure-on-error wiring.
- **That the scanner's signature database is current.** Vulnerability
  databases need updates to find new CVEs; out-of-date scanners
  produce false negatives.
- **That findings are reviewed and acted on.** The detector confirms
  scanning happens; the review and remediation loop is procedural.
- **That the workflow is wired into branch protection.** A scan on
  `main`-only doesn't block PRs that introduce vulnerabilities.
- **Notification agreements (SR-8) and contractual posture.** Those
  are procedural and outside CI-detectable signal.

## KSI mapping

**KSI-SCR-MON ("Monitoring Supply Chain Risk").** FRMR 0.9.43-beta
lists RA-5, SA-9, SI-5, SR-5, SR-6, SR-8, and others. This detector
evidences RA-5 directly. The other controls touch contractual /
procedural posture and remain candidates for repo-metadata detectors
that read `SECURITY.md`, `CODEOWNERS`, or vendor-attestation files.

## Tools recognized

`run:` step substrings:

| Tool | What it does |
|---|---|
| `syft` | SBOM generation (Anchore) |
| `cyclonedx` | CycloneDX-format SBOM generation |
| `grype` | Vulnerability scanning (Anchore) |
| `trivy fs` | Filesystem-mode vulnerability scanning (Aqua) |
| `trivy image` | Container-image vulnerability scanning |
| `snyk test` / `snyk monitor` | Snyk's security testing |
| `pip-audit` | Python dependency auditing |
| `npm audit` / `yarn audit` | Node.js dependency auditing |
| `cargo audit` | Rust dependency auditing |
| `osv-scanner` | Google OSV-based scanning |

`uses:`-action substrings (canonical-tool name attributed):

| Action prefix | Canonical |
|---|---|
| `anchore/syft-action` | syft |
| `anchore/scan-action` | grype |
| `aquasecurity/trivy-action` | trivy |
| `snyk/actions` | snyk |
| `ossf/scorecard-action` | ossf-scorecard |
| `actions/dependency-review-action` | github-dependency-review |
| `github/codeql-action` | codeql |

## States

| `monitoring_state` | Meaning |
|---|---|
| `present` | At least one SBOM or CVE-scan tool detected → evidences RA-5 |
| `absent` | No tooling detected → no evidence for KSI-SCR-MON |

## Example

Input (`.github/workflows/security.yml`):

```yaml
name: Security
on: [pull_request, schedule]
jobs:
  sbom_and_scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anchore/syft-action@v1
      - run: grype dir:.
      - run: pip-audit
      - uses: ossf/scorecard-action@v2
```

Output:

```json
{
  "detector_id": "github.supply_chain_monitoring",
  "ksis_evidenced": ["KSI-SCR-MON"],
  "controls_evidenced": ["RA-5"],
  "content": {
    "resource_type": "github_workflow",
    "resource_name": "Security",
    "sbom_tools_detected": ["syft"],
    "cve_scan_tools_detected": ["grype", "ossf-scorecard", "pip-audit"],
    "monitoring_state": "present"
  }
}
```

## Fixtures

- `fixtures/should_match/sbom_and_scan.yml` — workflow with SBOM +
  scanners → `monitoring_state="present"`.
- `fixtures/should_not_match/lint_only.yml` — workflow with linting
  but no supply-chain tooling → `monitoring_state="absent"` with gap.
