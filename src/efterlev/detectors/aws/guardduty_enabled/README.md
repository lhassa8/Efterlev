# `aws.guardduty_enabled`

Evidences that AWS GuardDuty is enabled for the account.

## What this detector evidences

- **KSI-MLA-OSM** (Operating SIEM Capability).
- **800-53 controls:** SI-4, RA-5(11).

## What it proves

At least one `aws_guardduty_detector` resource is declared with `enable = true` (or `enable` omitted, since AWS treats that as enabled).

## What it does NOT prove

- That the GuardDuty findings are routed to any human or automated response.
- That the detector covers all regions the workload spans — GuardDuty is per-region; multi-region setups need detectors per region.
- That the org-admin account model is set up for cross-account visibility.
- That the account is actually enrolled with AWS (a declared `enable = true` resource still depends on Terraform apply succeeding; the detector infers intent, not runtime state).

## Detection signal

- `enable = true` or attribute absent → emit Evidence with `detector_state="enabled"`.
- `enable = false` → no Evidence (explicit opt-out).

## Known limitations

- Multi-region coverage isn't checked. A single-region `aws_guardduty_detector` resource in a multi-region workload is technically partial coverage; the Gap Agent is the place where that nuance gets evaluated.
