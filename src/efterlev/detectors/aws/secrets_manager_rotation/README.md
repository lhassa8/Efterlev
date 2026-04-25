# `aws.secrets_manager_rotation`

Inspects Secrets Manager rotation configuration and surfaces secrets without rotation.

## What this detector evidences

- **KSI-SVC-ASM** (Automating Secret Management) and **KSI-IAM-SNU** (Securing Non-User Authentication).
- **800-53 controls:** SC-12, IA-5(1).

## What it proves

- For each `aws_secretsmanager_secret_rotation`: the rotation window (`automatically_after_days`), whether a rotation Lambda is set, and whether the window meets FedRAMP's recommended ≤90-day cadence for credential secrets.
- For each `aws_secretsmanager_secret` declared without a paired rotation resource: a negative-shape Evidence record flagging unrotated state.

## What it does NOT prove

- That the rotation Lambda is correctly implemented — that's a code review, not an IaC scan.
- That all secrets in use are managed via Secrets Manager (some workloads put secrets in SSM Parameter Store, env files, HashiCorp Vault — out of scope for this detector).
- That rotation actually executes successfully at runtime; only the configuration is visible to IaC.

## Detection signal

- `automatically_after_days ≤ 90` → `rotation_state = "configured_within_recommended"`.
- `automatically_after_days > 90` → `rotation_state = "configured_window_too_long"` with a gap message.
- Window unparseable → `rotation_state = "configured_unknown_window"`.
- Secret without paired rotation → `rotation_state = "absent"`.

The detector pairs secrets and rotations heuristically by name substring. Cross-reference can be improved if customers report mispairing.

## Known limitations

- Pairing heuristic is name-based and may miss rotations that reference secrets via `aws_secretsmanager_secret.X.id`. The `aws_secretsmanager_secret_rotation.secret_id` attribute is opaque from HCL alone when it's an interpolation.
- The 90-day threshold is FedRAMP guidance, not absolute. Workloads with documented compensating controls (HSM-backed keys, etc.) may legitimately exceed it; the Gap Agent is the right place to evaluate context.
