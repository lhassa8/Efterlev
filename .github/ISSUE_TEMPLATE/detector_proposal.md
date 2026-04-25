---
name: New detector proposal
about: Propose a new detector for the library.
title: "detectors: aws.<capability>"
labels: ["detector", "good first issue"]
assignees: []
---

## Capability

What compliance-relevant pattern does this detector check for?

## Resource type(s)

Which Terraform resource type(s) does it inspect? (e.g., `aws_s3_bucket`, `aws_cloudtrail`)

## KSI / control mapping

- KSI: (or "none — see SC-28 precedent")
- 800-53 controls: (e.g., AU-2, AU-12)

If the detector evidences a control with no KSI mapping in FRMR 0.9.43-beta, follow the existing `aws.encryption_s3_at_rest` precedent — declare `ksis=[]` and explain in the README. Do not invent a KSI.

## What it proves

A specific, narrow statement. "Bucket has SSE configured" is fine; "bucket is FedRAMP-compliant" is not.

## What it does NOT prove

The hard part. Be specific about layer (infrastructure vs procedural), scope (per-resource vs cross-resource), runtime vs config, and any limits of static IaC parsing.

## Fixture sketch

- `should_match/`: 1–3 .tf cases that exercise the positive evidence path.
- `should_not_match/`: 1–2 .tf cases with related but non-matching configurations.

If `jsonencode(...)` or `data.<ref>.json` would render the detector signal as `${...}`, plan a `unparseable` evidence variant.

## Anything you've already tried

Hand-walked Terraform fixtures? Read CONTRIBUTING.md? Looked at the existing detectors?

---

Acceptance is at the maintainer's discretion per [GOVERNANCE.md](https://github.com/efterlev/efterlev/blob/main/GOVERNANCE.md). PRs implementing accepted proposals are welcome — the detector contract in [CONTRIBUTING.md](https://github.com/efterlev/efterlev/blob/main/CONTRIBUTING.md) is the path from accepted proposal to merged PR.
