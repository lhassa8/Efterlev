# `aws.access_analyzer_enabled`

Evidences that IAM Access Analyzer is configured.

## What this detector evidences

- **KSI-CNA-EIS** (Enforcing Intended State).
- **800-53 controls:** CA-7 (Continuous Monitoring), AC-6 (Least Privilege).

## What it proves

An `aws_accessanalyzer_analyzer` resource is declared in the Terraform, with either `ACCOUNT` (default) or `ORGANIZATION` scope.

## What it does NOT prove

- That the findings produced by the analyzer are reviewed.
- That the scope chosen matches the compliance boundary — an ACCOUNT-scoped analyzer in a multi-account FedRAMP boundary misses cross-account findings.
- That any remediation workflow responds to findings.

## Detection signal

Every `aws_accessanalyzer_analyzer` resource produces one Evidence record. `scope = "ORGANIZATION"` is captured as stronger evidence (broader coverage) than the default `"ACCOUNT"` scope.

## Known limitations

- The detector evidences declaration only. Analyzer enablement state (`status`) is not checked — AWS enables analyzers on creation.
- A FedRAMP boundary spanning multiple accounts should use `ORGANIZATION` scope from the management account; ACCOUNT-only scope is weaker evidence but still evidence. The Gap Agent contextualizes.
