# github.immutable_deploy_patterns

Detects whether `.github/workflows/*.yml` workflows include declarative-
deploy tooling (terraform apply, helm upgrade, kubectl apply, etc.).
KSI-CMT-RMV ("Redeploying vs Modifying") asks the customer to *execute
changes through redeployment of version controlled immutable resources
rather than direct modification of running systems* — declarative-
deploy tools are the canonical IaC-evidenceable signal.

## What it proves

- **CM-2 (Configuration Baseline)** — declarative-deploy tools re-apply
  a versioned baseline on every run.
- **CM-7 (Least Functionality)** — declarative deploys deliver only
  what's declared in source.

## What it does NOT prove

- **That the workflow lacks imperative side-edits.** Anti-pattern
  detection (kubectl edit, aws ... modify-*) is deferred to a
  follow-up detector.
- **That deploys are wired into branch protection.** A declarative
  workflow that anyone can run from any branch is weaker than one
  required-on-merge to main.
- **That production deploys actually go through this workflow.**
  Manual console operations, CLI scripts, or other deploy paths
  remain invisible.

## KSI mapping

**KSI-CMT-RMV ("Redeploying vs Modifying").** FRMR 0.9.43-beta lists
CM-2, CM-3, CM-5, CM-6, CM-7, CM-8(1), SI-3 in this KSI's `controls`
array. This detector evidences CM-2 and CM-7 directly. Other controls
(CM-5 access enforcement for change control, SI-3 malicious-code
protection) are adjacent and remain candidates for sibling detectors.

## Tools recognized

`run:` step substrings:
- `terraform apply`, `pulumi up`, `cdk deploy` (IaC)
- `helm upgrade`, `helm install`, `kubectl apply`, `kustomize build` (k8s)
- `argocd app sync`, `fluxctl sync` (GitOps)

`uses:`-action substrings (mapped to canonical-tool names):
- `hashicorp/setup-terraform` → `terraform`
- `azure/k8s-deploy` → `kubectl apply`
- `azure/setup-helm` → `helm`
- `WyriHaximus/github-action-helm3` → `helm`

## States

| `redeploy_pattern_state` | Meaning | Controls evidenced |
|---|---|---|
| `present` | ≥1 declarative tool detected | CM-2, CM-7 |
| `absent` | No declarative tools | (gap; no evidence) |

## Example

Input (`.github/workflows/deploy.yml`):

```yaml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  apply:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: terraform apply -auto-approve
```

Output:

```json
{
  "detector_id": "github.immutable_deploy_patterns",
  "ksis_evidenced": ["KSI-CMT-RMV"],
  "controls_evidenced": ["CM-2", "CM-7"],
  "content": {
    "resource_type": "github_workflow",
    "resource_name": "Deploy",
    "declarative_tools_detected": ["terraform", "terraform apply"],
    "redeploy_pattern_state": "present"
  }
}
```

## Fixtures

- `fixtures/should_match/declarative_deploy.yml` — terraform apply
  workflow → `redeploy_pattern_state="present"`.
- `fixtures/should_not_match/lint_only.yml` — no deploy steps →
  `redeploy_pattern_state="absent"` with gap.
