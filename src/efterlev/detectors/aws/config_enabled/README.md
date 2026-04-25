# `aws.config_enabled`

Evidences that AWS Config is recording resource state.

## What this detector evidences

- **KSI-MLA-EVC** (Evaluating Configurations), **KSI-SVC-ACM** (Automating Configuration Management).
- **800-53 controls:** CM-2, CM-8(2).

## What it proves

Both `aws_config_configuration_recorder` AND `aws_config_delivery_channel` resources are declared in the Terraform. AWS Config needs both to actually record — a recorder without a delivery channel produces nothing, and vice versa.

## What it does NOT prove

- That recorded changes are reviewed by anyone.
- That Config rules are evaluating compliance against the recorded state (a separate `aws_config_config_rule` resource would be needed).
- That the delivery-channel S3 bucket is itself secured (separate detector: `aws.encryption_s3_at_rest`, `aws.s3_public_access_block`).
- That the recorder has been started via `aws_config_recorder_status` (AWS split the start/stop step out — Terraform-declared `configuration_recorder` defaults to started, but not always).

## Detection signal

- Recorder + channel both present → one Evidence per recorder, with `recorder_state="recording"`, `coverage` reflecting `recording_group.all_supported`, and `delivery_channel_count` capturing the pairing.
- Recorder present, no channel → no Evidence (Config doesn't function without a delivery channel).
- Channel present, no recorder → no Evidence (same reason, other direction).

## Known limitations

- Cross-resource pairing is coarse — any recorder is paired with all declared channels in the same scan. This matches real AWS Config semantics (there's at most one recorder per account/region, so ambiguity is rare in practice).
- The `aws_config_recorder_status` resource's `is_enabled` attribute isn't checked; a recorder defined but never started would still emit Evidence here. Flagged as a known gap; revisit if customer feedback calls it out.
