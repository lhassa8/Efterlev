# `aws.backup_restore_testing`

Inspects every `aws_backup_restore_testing_plan` and emits one Evidence per plan, characterizing whether the plan is fully wired (schedule + selection) versus configured-but-incomplete.

## What this detector evidences

- **KSI-RPL-TRC** (Testing Recovery Capabilities).
- **800-53 controls:** CP-4 (Contingency Plan Testing), CP-4(1) (Coordinate with Related Plans).

## What it proves

For each `aws_backup_restore_testing_plan` resource, the detector checks:

1. The plan has a `schedule_expression` (cron or rate). Without one, the plan never fires.
2. At least one `aws_backup_restore_testing_selection` references this plan via `restore_testing_plan_id = aws_backup_restore_testing_plan.<name>.id`. Without a selection, the plan fires but tests nothing.

When both are present, `testing_state = "configured"`. Otherwise the gap field names what's missing.

## Why this matters

Existing AWS Backup detectors (e.g., `aws.backup_retention_configured` for KSI-RPL-ABO) prove backups *exist*. Existence isn't proof of recoverability — backups are notorious for failing the first time they're actually needed. AWS introduced Restore Testing in 2023 specifically to close this gap: it's the cloud-native primitive for *automated, scheduled, verifiable* recovery validation.

KSI-RPL-TRC asks customers to "persistently test the capability to recover from incidents and contingencies, including alignment with defined recovery objectives." A scheduled `aws_backup_restore_testing_plan` with a real selection is the canonical IaC-evidenceable signal.

## What it does NOT prove

- That past test restores have actually succeeded — runtime artifacts live in AWS Backup, outside the IaC layer. The Documentation Agent should narrate that.
- That the tested recovery points reflect production data (the selection's `recovery_point_types` knob bounds this; we surface it as evidence content but don't classify on it).
- That recovery objectives (RTO/RPO) are met by the schedule cadence — that's a reviewer concern, since IaC has no way to express the customer's RTO target.
- That `aws_backup_restore_testing_inferred_metadata` is wired — the detector doesn't require it.

## Detection signal

One Evidence record per `aws_backup_restore_testing_plan`. The `gap` field populates when `testing_state ∈ {no_selection, incomplete}` and names the specific missing piece.

## Known limitations

- Selections matched to plans by Terraform-reference name. Selections that reference a plan via `data.aws_backup_restore_testing_plan` (rare) won't match by name; they'd need a different join mechanism.
- The `aws_backup_restore_testing_selection` resource is itself a separate detector concern (whether the selection covers the right recovery points / ages); we surface the count and selection_window_days for the Gap Agent to reason over.
