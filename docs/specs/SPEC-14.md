# SPEC-14: A4 detector breadth — 16 detectors to reach 30

**Status:** implemented 2026-04-25 — all 16 detectors landed; total detector count 30; 602 tests passing
**Gate:** A4
**Depends on:** none (uses existing `@detector` contract documented in `CONTRIBUTING.md`)
**Blocks:** Launch (gate A4 exit criterion is "30 detectors covering 9 of 11 KSI themes")
**Size:** L when measured by detector count; each individual detector is S. Implementation is naturally batched.

## Why one omnibus spec instead of 16 files

Each detector follows the same contract (`detector.py` + `mapping.yaml` + `evidence.yaml` + `fixtures/` + `README.md`) and produces the same shape of evidence record. Per-detector content that varies is mostly: which resource types are inspected, the boolean condition, KSI/control mapping, and the explicit "what this does not prove" language. That's compact — 15–25 lines per detector, not a full SPEC template each.

Sixteen separate spec files would repeat the @detector contract 16 times for no gain. This omnibus collects per-detector specs as sub-sections, keeps the shared parts shared, and lets the implementation track all 16 against a single document. When the detector library grows further post-launch (Phase 6's longer tail), the same pattern applies.

## Goal

Add 16 AWS-Terraform detectors so the v0.1.0 launch covers 30 detectors total, spanning 9 of 11 FRMR-Moderate KSI themes. A first-time user scanning their real AWS-Terraform infra sees coverage they recognize, not a toy.

## Shared scope (applies to every detector below)

- AWS-only at v0.1.0 (multi-cloud is post-launch C3).
- HCL parsing AND plan-JSON parsing both supported per the v0 plan-JSON work; every detector ships an HCL fixture pair AND a plan-JSON-equivalent fixture pair, with an equivalence test.
- Detector ID is capability-shaped (`aws.<capability>`), not control-numbered (per the existing convention).
- Each detector's docstring includes the required "does NOT prove" section.
- Where FRMR has no KSI mapping the underlying control (SC-28 precedent), `ksis=[]` and the README explains the FRMR mapping gap honestly.

## Shared non-goals (applies to every detector below)

- Runtime cloud-API scanning. v1.5+.
- Cross-account or cross-region scope analysis (a detector that says "this account uses good encryption" by inspecting many resources in tandem). Each detector is single-resource-shaped.
- LLM-assisted detection. Detectors are deterministic by contract.
- Auto-remediation diffs at detector time (the Remediation Agent owns the diff workflow).

## Shared exit criteria for each detector below

- [ ] `src/efterlev/detectors/aws/<capability>/detector.py` exists and matches the `@detector` decorator contract (`id`, `ksis`, `controls`, `source="terraform"`, `version="0.1.0"`).
- [ ] `mapping.yaml`, `evidence.yaml`, `fixtures/should_match/*.tf`, `fixtures/should_not_match/*.tf`, and `README.md` all present.
- [ ] Plan-JSON equivalence fixtures present alongside HCL fixtures; equivalence test in `tests/detectors/test_<capability>.py` passes for both modes.
- [ ] Detector unit tests in `tests/detectors/` cover at least one positive evidence case and one negative-or-no-evidence case.
- [ ] Docstring "does NOT prove" section is honest and specific.
- [ ] Detector imported and registered via the existing `detectors/__init__.py` pattern.

## Detector backlog (16)

Ordered by family. Each sub-section is the per-detector spec; check off as it lands.

### Network-boundary family — SC-7 (4 detectors)

#### SPEC-14.1 — `aws.security_group_open_ingress` ✅ (landed 2026-04-24)

- **Detection signal:** any `aws_security_group` or `aws_security_group_rule` with `cidr_blocks` containing `0.0.0.0/0` on a non-essential port. "Non-essential" excludes commonly-internet-facing ports (80/443) where 0.0.0.0/0 is normal; includes everything else (22, 3389, 27017, 5432, 6379, etc.).
- **Resource types:** `aws_security_group`, `aws_security_group_rule`.
- **KSI:** KSI-SVC-* if a network-boundary KSI exists in FRMR 0.9.43-beta; otherwise `ksis=[]` per the SC-28 precedent.
- **800-53:** SC-7, SC-7(3) (boundary protection).
- **What it proves:** an SG rule with `0.0.0.0/0` ingress on a non-essential port is present in the Terraform.
- **What it does NOT prove:** that the SG is attached to anything reachable; that the port is actually open to the public internet through the upstream VPC topology; that the application listening on the port doesn't enforce its own auth.
- **Edge cases:** `0.0.0.0/0` on 80/443 is allowed (public web traffic); `::/0` IPv6 equivalent is treated identically; `prefix_list_ids` is opaque from HCL alone — flagged with `unparseable` evidence variant.
- **Fixture plan:** SG with 22 open to world (matches); SG with 22 open to a single CIDR (no match); SG with 443 open to world (no match); SG with 22 open to `prefix_list_ids` (unparseable).

#### SPEC-14.2 — `aws.rds_public_accessibility` ✅ (landed 2026-04-24)

- **Detection signal:** `aws_db_instance` or `aws_rds_cluster` with `publicly_accessible = true`.
- **Resource types:** `aws_db_instance`, `aws_rds_cluster`, `aws_rds_cluster_instance`.
- **KSI:** TBD — likely KSI-SVC-* boundary-related.
- **800-53:** AC-3, SC-7.
- **What it proves:** an RDS instance is configured with public-network reachability in the Terraform.
- **What it does NOT prove:** that the security groups attached to the RDS allow internet ingress; or that data ever crosses the boundary even if access is granted.
- **Edge cases:** unset `publicly_accessible` defaults to `false` — that's a no-match. `(known after apply)` from plan JSON treated as unparseable.
- **Fixture plan:** publicly-accessible RDS (matches); private RDS with explicit false (no match); RDS with absent flag (no match); RDS with unparseable plan-JSON value (unparseable evidence variant).

#### SPEC-14.3 — `aws.s3_bucket_public_acl` ✅ (landed 2026-04-24)

- **Detection signal:** `aws_s3_bucket_acl` with `acl` set to `public-read`, `public-read-write`, or any policy referencing the `AllUsers` group. Complements the existing `aws.s3_public_access_block` detector by catching the bucket-ACL path explicitly.
- **Resource types:** `aws_s3_bucket_acl`, `aws_s3_bucket_policy`.
- **KSI:** KSI-SVC-*.
- **800-53:** SC-7, AC-3.
- **What it proves:** a bucket ACL or bucket policy in the Terraform makes the bucket publicly readable or writable.
- **What it does NOT prove:** that the bucket actually contains anything sensitive; that the bucket isn't covered by an `aws_s3_bucket_public_access_block` that overrides the ACL (note: PAB does override ACLs, but the warning still has value as a signal of intent).
- **Edge cases:** policies built via `data.aws_iam_policy_document` may render as `${...}` placeholders → unparseable.
- **Fixture plan:** bucket ACL set to `public-read` (matches); bucket ACL set to `private` (no match); bucket policy granting Principal `*` (matches); jsonencoded policy doc (unparseable).

#### SPEC-14.4 — `aws.nacl_open_egress` ✅ (landed 2026-04-24)

- **Detection signal:** `aws_network_acl_rule` (or inline `egress` block in `aws_network_acl`) allowing `0.0.0.0/0` outbound on `protocol = "-1"` (all traffic).
- **Resource types:** `aws_network_acl`, `aws_network_acl_rule`.
- **KSI:** KSI-SVC-*.
- **800-53:** SC-7.
- **What it proves:** a NACL allows broad egress to the internet.
- **What it does NOT prove:** that any subnet uses this NACL; that egress isn't otherwise constrained by route tables, NAT gateway absence, or organizational SCPs.
- **Edge cases:** the AWS default NACL has 0.0.0.0/0 egress allowed by default; flagging the *default* NACL as a finding generates noise. The detector inspects only resources explicitly defined in the Terraform — if the user hasn't authored an `aws_network_acl` resource, no evidence is emitted.
- **Fixture plan:** NACL with broad egress (matches); NACL with restricted egress (no match); NACL with 0.0.0.0/0 on a specific protocol like 443 (no match — only `-1` all-protocols matches).

### Monitoring & alerting family — SI-4, AU-2 (4 detectors)

#### SPEC-14.5 — `aws.cloudwatch_alarms_critical` ✅ (landed 2026-04-24)

- **Detection signal:** presence of `aws_cloudwatch_metric_alarm` resources alarming on critical-event metric names (RootAccountUsage, IAMPolicyChanges, UnauthorizedAPICalls, ConsoleLoginsWithoutMFA — the FedRAMP-recommended set).
- **Resource types:** `aws_cloudwatch_metric_alarm`, `aws_cloudwatch_log_metric_filter`.
- **KSI:** KSI-MLA-OSM or KSI-MLA-LET.
- **800-53:** SI-4(2), SI-4(4), AU-6(1).
- **What it proves:** alarms exist for the specific FedRAMP-recommended events in the Terraform.
- **What it does NOT prove:** that the alarms have valid SNS subscriptions; that the SNS topic is monitored; that someone reads the alerts; that the metric filter pattern actually matches what it's intended to.
- **Edge cases:** alarm count is graded — full set vs partial set vs none. The detector emits one evidence record per recommended alarm, with `present`/`absent` markers, so the Gap Agent can render a per-alarm table.
- **Fixture plan:** all four alarms present (full match); only RootAccountUsage (partial match); none of them (no positive matches; one negative-summary record).

#### SPEC-14.6 — `aws.guardduty_enabled` ✅ (landed 2026-04-24)

- **Detection signal:** at least one `aws_guardduty_detector` with `enable = true`.
- **Resource types:** `aws_guardduty_detector`, `aws_guardduty_organization_admin_account`.
- **KSI:** KSI-MLA-*.
- **800-53:** SI-4, RA-5(11).
- **What it proves:** GuardDuty is configured to run in the Terraform.
- **What it does NOT prove:** that findings are routed anywhere humans see them; that the detector covers all regions the workload spans; that the org-admin account model is set up for cross-account visibility.
- **Edge cases:** `enable = false` is an explicit non-match; absent `aws_guardduty_detector` resource is also a non-match. Multi-region setups need detectors per region — single-region detection only emits one record.
- **Fixture plan:** detector enabled (match); detector disabled (no match); no detector resource at all (no match).

#### SPEC-14.7 — `aws.config_enabled` ✅ (landed 2026-04-24)

- **Detection signal:** `aws_config_configuration_recorder` with `recording_group.all_supported = true` AND `aws_config_delivery_channel` configured.
- **Resource types:** `aws_config_configuration_recorder`, `aws_config_delivery_channel`, `aws_config_recorder_status`.
- **KSI:** TBD — possibly unmapped (CM-2 doesn't always have a KSI in FRMR 0.9.43-beta).
- **800-53:** CM-2, CM-8(2).
- **What it proves:** AWS Config is recording resource state changes.
- **What it does NOT prove:** that recorded changes are reviewed; that any Config rules are evaluating compliance; that the delivery channel's S3 bucket is itself secure.
- **Edge cases:** `recording_group.all_supported = false` with a custom resource list is treated as partial coverage (evidence variant).
- **Fixture plan:** recorder + delivery channel both configured (match); recorder only (no match); neither (no match).

#### SPEC-14.8 — `aws.access_analyzer_enabled` ✅ (landed 2026-04-24)

- **Detection signal:** `aws_accessanalyzer_analyzer` with `type = "ACCOUNT"` (or `"ORGANIZATION"`).
- **Resource types:** `aws_accessanalyzer_analyzer`.
- **KSI:** TBD — CA-7 ("continuous monitoring") may not have a clean KSI in FRMR 0.9.43-beta.
- **800-53:** CA-7, AC-6.
- **What it proves:** IAM Access Analyzer is configured.
- **What it does NOT prove:** that findings are reviewed; that the analyzer covers the right scope (account vs org).
- **Edge cases:** ORGANIZATION type is stricter and emitted as a higher-quality evidence variant.
- **Fixture plan:** account-scoped analyzer (match); org-scoped analyzer (match, higher quality variant); no analyzer (no match).

### Key management family — SC-12, SC-28 (4 detectors)

#### SPEC-14.9 — `aws.kms_customer_managed_keys` ✅ (landed 2026-04-25)

- **Detection signal:** `aws_kms_key` resources with explicit creation (CMK), as opposed to references to AWS-managed keys (`alias/aws/...`).
- **Resource types:** `aws_kms_key`, `aws_kms_alias`.
- **KSI:** KSI-SVC-VRI (validating resource integrity via cryptography).
- **800-53:** SC-12.
- **What it proves:** the Terraform creates customer-managed KMS keys for cryptographic operations.
- **What it does NOT prove:** that the keys are actually used by the resources that should use them; key rotation policy (covered by `aws.kms_key_rotation`); key-deletion lifecycle.
- **Edge cases:** complements the existing `aws.kms_key_rotation` detector — this one inventories CMKs; the existing one checks rotation per-key.
- **Fixture plan:** CMK with policy and alias (match); resource using AWS-managed key alias only (no CMK match).

#### SPEC-14.10 — `aws.secrets_manager_rotation` ✅ (landed 2026-04-25)

- **Detection signal:** `aws_secretsmanager_secret_rotation` configured with `rotation_rules.automatically_after_days <= 90` AND a `rotation_lambda_arn` set.
- **Resource types:** `aws_secretsmanager_secret`, `aws_secretsmanager_secret_rotation`.
- **KSI:** TBD — possibly KSI-SVC-VRI extended or unmapped per the SC-12 mapping pattern.
- **800-53:** SC-12, IA-5(1).
- **What it proves:** automatic rotation is configured for at least one secret.
- **What it does NOT prove:** that the rotation Lambda is correctly implemented (that's a code review, not an IaC scan); that all secrets are rotated (only those with explicit rotation resources).
- **Edge cases:** secrets without rotation resources are emitted as negative-evidence with `rotation_state="absent"`. The detector aggregates per-secret evidence so the Gap Agent can render a per-secret table.
- **Fixture plan:** secret with 30-day rotation (match); secret without rotation resource (negative); rotation set to 365 days (out-of-range — emit `rotation_too_long`).

#### SPEC-14.11 — `aws.sns_topic_encryption` ✅ (landed 2026-04-25)

- **Detection signal:** `aws_sns_topic` with `kms_master_key_id` set to a customer-managed key (not the default `alias/aws/sns`).
- **Resource types:** `aws_sns_topic`.
- **KSI:** TBD — same SC-28 precedent treatment.
- **800-53:** SC-28.
- **What it proves:** the SNS topic uses CMK-based encryption at rest.
- **What it does NOT prove:** that subscribers' inboxes are also encrypted; that the messages are encrypted in transit (different control: SC-8 on the subscriber side).
- **Edge cases:** absent `kms_master_key_id` defaults to AWS-managed encryption — emitted as `encryption_state="aws_managed"` rather than absent (FedRAMP accepts AWS-managed but customer-managed is preferred).
- **Fixture plan:** topic with CMK reference (match); topic with AWS-managed default (partial match); topic with no encryption attribute (default — partial match).

#### SPEC-14.12 — `aws.sqs_queue_encryption` ✅ (landed 2026-04-25)

- **Detection signal:** `aws_sqs_queue` with `kms_master_key_id` set to a CMK.
- **Resource types:** `aws_sqs_queue`.
- **KSI:** TBD — same SC-28 precedent.
- **800-53:** SC-28.
- **What it proves:** the SQS queue uses CMK encryption at rest.
- **What it does NOT prove:** that producers/consumers handle messages securely after dequeue.
- **Edge cases:** mirror of SPEC-14.11 (SNS pattern).
- **Fixture plan:** queue with CMK (match); queue with AWS-managed default (partial); queue without encryption attribute (partial).

### IAM depth family — IA-2, AC-6 (3 detectors)

#### SPEC-14.13 — `aws.iam_inline_policies_audit` ✅ (landed 2026-04-25)

- **Detection signal:** presence of `aws_iam_role_policy`, `aws_iam_user_policy`, or `aws_iam_group_policy` (inline-policy resources). Inline policies are an anti-pattern compared to managed policies because they're invisible from the IAM console outside their attached identity.
- **Resource types:** `aws_iam_role_policy`, `aws_iam_user_policy`, `aws_iam_group_policy`.
- **KSI:** TBD — IAM-related; possibly KSI-IAM-*.
- **800-53:** AC-6, AC-2.
- **What it proves:** inline policies are present.
- **What it does NOT prove:** that the inline policy itself grants overly-broad permissions (the policy contents are flagged as `unparseable` if they use `jsonencode` or `data.aws_iam_policy_document`); that there's actually a problem — inline can be the right answer for tightly-scoped one-off bindings.
- **Edge cases:** this is a "warning" detector, not a "finding" one. Evidence emits with a softer severity; the Gap Agent renders as informational.
- **Fixture plan:** role with inline policy (match, warning); role with managed policy (no match); user with inline (match).

#### SPEC-14.14 — `aws.iam_admin_policy_usage` ✅ (landed 2026-04-25)

- **Detection signal:** any IAM principal (role, user, group) with the AWS-managed `AdministratorAccess` policy attached.
- **Resource types:** `aws_iam_role_policy_attachment`, `aws_iam_user_policy_attachment`, `aws_iam_group_policy_attachment`.
- **KSI:** TBD — IAM-related.
- **800-53:** AC-6, AC-6(2).
- **What it proves:** AdministratorAccess is attached to at least one principal.
- **What it does NOT prove:** that the principal is actually used; that the privilege is unjustified (emergency-break-glass roles legitimately have this).
- **Edge cases:** the detector emits per-principal evidence so the Gap Agent can highlight which principals carry the privilege; the agent then makes the human-judgment call about justification.
- **Fixture plan:** role with AdministratorAccess attachment (match); role with custom policy (no match).

#### SPEC-14.15 — `aws.iam_service_account_keys_age` ✅ (landed 2026-04-25)

- **Detection signal:** `aws_iam_access_key` resources for IAM users — long-lived access keys for service-account-shaped users (no console password) are an anti-pattern; AWS recommends rotating them within 90 days, but Terraform doesn't carry creation date so we evidence the *presence* of access keys for users without console passwords.
- **Resource types:** `aws_iam_access_key`, `aws_iam_user`, `aws_iam_user_login_profile`.
- **KSI:** KSI-IAM-MFA (related; phishing-resistant identity).
- **800-53:** IA-2, IA-5.
- **What it proves:** an IAM user has long-lived access keys configured in the Terraform.
- **What it does NOT prove:** the key's age (not visible from IaC); whether the key is actually used; whether the user has MFA enforced (covered by `aws.mfa_required_on_iam_policies`).
- **Edge cases:** users with login profiles AND access keys are treated as human users with extra power — evidence emits with that distinction.
- **Fixture plan:** user with access_key + no login_profile (match — service account); user with login_profile only (no access-key match); user with both (match — human-user-with-keys variant).

### Logging family — AU-2, AU-11 (1 detector)

#### SPEC-14.16 — `aws.elb_access_logs` ✅ (landed 2026-04-25)

- **Detection signal:** `aws_lb` (Application or Network) with `access_logs.enabled = true` and a configured `access_logs.bucket`.
- **Resource types:** `aws_lb`, `aws_alb` (legacy alias).
- **KSI:** KSI-MLA-LET (logging event types).
- **800-53:** AU-2, AU-12.
- **What it proves:** access logs are enabled for the load balancer.
- **What it does NOT prove:** that the destination S3 bucket is itself encrypted, retained appropriately, or has lifecycle policies; that anyone reads the logs.
- **Edge cases:** classic ELBs (`aws_elb`) use a different attribute path (`access_logs.bucket`) — covered by the same detector with a slightly different rule branch.
- **Fixture plan:** ALB with access_logs enabled (match); ALB without the access_logs block (no match); classic ELB with access_logs (match).

## Roll-up exit criterion (gate A4)

- [ ] All 16 detectors above implemented per their per-detector exit criteria.
- [ ] Total detector count = 30 (14 existing + 16 new).
- [ ] Detector coverage spans 9 of 11 KSI themes; the 2 themes not covered (likely procedural-only ones from the AFR / KSO themes) named explicitly in `LIMITATIONS.md`.
- [ ] All detectors registered via `src/efterlev/detectors/__init__.py`.
- [ ] All HCL/plan-JSON equivalence tests pass.
- [ ] Total test count grows by ~64 (4 tests/detector × 16 detectors), exact count in the implementation summary.
- [ ] `LIMITATIONS.md` updated to reflect the 30-detector reality and the residual procedural coverage gap.
- [ ] `README.md` "Current coverage" section updated to list the 30 detectors.

## Risks

- **KSI mapping uncertainty.** Several detectors above flag KSI as `TBD` or `(unmapped — see precedent)`. Where FRMR 0.9.43-beta has no clean KSI for a control, we use `ksis=[]` and flag the gap honestly per the SC-28 precedent. This is the project's discipline; it's not a defect to be fixed by inventing a KSI.
- **Detector scope creep.** Each detector is single-resource-shaped by design. PRs that try to make a detector inspect cross-resource state (e.g., "does the SG referenced by this RDS allow public access?") get redirected: that's the Gap Agent's job, not a detector's.
- **Plan-JSON parsing differences.** The `(known after apply)` placeholder in plan-JSON output must be handled identically to the HCL `${...}` interpolation case — both are "unparseable" evidence variants. Existing detectors handle this; new ones must too. The equivalence test catches divergence.
- **Fixture inflation.** 16 detectors × ~4 fixtures each = 64 .tf files. Keep each minimal (10–20 lines, named for the case it covers). Resist the urge to make fixtures realistic-shaped — that's the e2e harness's job.

## Open questions

- The exact KSI mapping for several SC-7 / IA-2 / AC-6 detectors is TBD. Resolve at implementation time by checking FRMR 0.9.43-beta directly. If no KSI fits, `ksis=[]` per precedent.
- Whether the warning-shaped detectors (`iam_inline_policies_audit`, `iam_admin_policy_usage`) emit at the same severity as finding-shaped detectors. Decision deferred to Gap Agent rendering work — the detector emits evidence; the agent classifies severity in context.
