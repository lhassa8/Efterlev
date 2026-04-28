# `aws.suspicious_activity_response`

Inspects every `aws_cloudwatch_event_rule` whose `event_pattern` matches a security-finding source (GuardDuty, Security Hub, Access Analyzer, Inspector v2, Macie v2) and joins matching `aws_cloudwatch_event_target` resources to verify that an automated response is wired.

## What this detector evidences

- **KSI-IAM-SUS** (Responding to Suspicious Activity).
- **800-53 controls:** AC-2 (Account Management — framing), AC-2(13) (Disable Accounts for High-Risk Individuals — the canonical mechanism).

## What it proves

For each EventBridge rule in the codebase:

1. Parse `event_pattern` (typically built via `jsonencode({ source = ["aws.guardduty"], ... })`).
2. If the `source` field includes any of `aws.guardduty`, `aws.securityhub`, `aws.access-analyzer`, `aws.inspector2`, `aws.macie2`, the rule is in scope.
3. Join `aws_cloudwatch_event_target` resources by `rule = aws_cloudwatch_event_rule.<name>.name`. Targets resolve to a target_summary like `lambda`, `sns`, `ssm-automation`.

`response_state = "wired"` when ≥1 target attaches; `"no_target"` otherwise.

## Why this matters

KSI-IAM-SUS asks customers to "automatically disable or otherwise secure accounts with privileged access in response to suspicious activity." The AWS-native IaC expression of this is an EventBridge rule fired by GuardDuty/Security Hub findings, with a Lambda or SSM Automation target that takes the account-disable / credential-revoke action. Without the target, the rule is silent — the finding is generated but no response runs.

This is a step beyond `aws.guardduty_enabled` (KSI-MLA-OSM, the *monitoring* signal). Monitoring without response is incomplete; this detector evidences the response side.

## What it does NOT prove

- That the target Lambda actually disables accounts vs. merely logging the event. The detector establishes the architectural pattern; runtime correctness of the response logic is outside what IaC can show.
- That the target's IAM role can take the disable action — that's an IAM-policy concern.
- That the rule's `event_pattern` is tuned correctly (e.g., only HIGH-severity GuardDuty findings vs. every finding) — the Gap Agent reasons over the matched_sources field.

## Detection signal

One Evidence record per finding-sourced rule. Rules whose event_pattern doesn't match a security-finding source emit no evidence — the detector is anchored on the architectural pattern, not every EventBridge rule.

## Known limitations

- `event_pattern` built via `data.aws_cloudwatch_event_pattern.x.json` or other indirection renders as a `${...}` placeholder from HCL alone; matching is conservative (no match → no evidence). Plan-JSON mode resolves the indirection.
- The detector doesn't validate that the matched source is *actually a security finding* — `aws.guardduty` events include benign administrative events (e.g., detector enable/disable). Conservatively, we treat any match against the source list as in-scope; the Gap Agent reads `event_pattern` content to refine.
