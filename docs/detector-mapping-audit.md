# Detector → KSI mapping audit (2026-04-29)

A systematic re-read of every KSI-mapped detector's primary KSI mapping
against that KSI's moderate-level statement (now visible after PR #82
lands the `varies_by_level` loader fix). The earlier audit covered
SVC-RUD and SVC-VCM (PR #83); this doc covers the remaining 34
KSI-mapped detectors.

**Scope:** documentary audit only. No mapping.yaml or decorator changes
in this PR. Findings here flag candidates for follow-up PRs the
maintainer can prioritize.

**Methodology:** for each detector, compared the FRMR moderate-level
statement to (a) what the detector's `detect()` function actually
evidences and (b) the FRMR catalog's `controls` array for that KSI.
Categorized each mapping as:

- ✅ **Direct fit** — the detector evidences the KSI's moderate outcome
  at the IaC layer with strong semantic overlap.
- 🟡 **Partial cross-mapping** — the detector evidences a slice of the
  KSI's outcome OR cross-maps via the FRMR `controls` linkage but not
  the full moderate statement. The mapping should carry explicit
  partial-coverage notes (matching the SVC-RUD/SVC-VCM treatment from
  PR #83).
- ⚠ **Reclassification candidate** — the detector and KSI don't share
  enough semantic overlap to justify the mapping. Worth re-thinking;
  may need to drop the mapping, re-home to a different KSI, or move to
  the supplementary 800-53-only cohort.

---

## Summary

Of 34 detectors audited (excluding the 2 already covered in PR #83):

- **23 ✅ Direct fits.** Mappings are clean.
- **9 🟡 Partial cross-mappings.** Recommend explicit partial-coverage
  notes in mapping.yaml + README, matching PR #83's treatment.
- **2 ⚠ Reclassification candidates.** Worth maintainer judgment on
  whether to keep, re-home, or move to ksis=[].

Direct-fit detectors are listed in the appendix without per-detector
narrative. Partial cross-mappings and reclassification candidates each
get a section explaining the mismatch.

---

## Partial cross-mappings (9)

Each of these has a real catalog cross-reference (the FRMR `controls`
array supports the link), but the detector evidences a *slice* of the
KSI's moderate-level outcome rather than the full outcome. Recommend
follow-up PRs that add `coverage: partial` + explicit notes to each
detector's mapping.yaml + README.

### 1. `aws.cloudtrail_audit_logging` → KSI-MLA-LET

**Moderate:** *"Maintain a list of information resources and event types
that will be logged, monitored, and audited, then do so."*

**Detector evidences:** AWS API control-plane events captured by
CloudTrail.

**Slice:** CloudTrail covers control-plane events only — application
logs, OS audit logs, database audit logs are uncovered. The KSI's "list
of information resources" is broader than the AWS API surface.

**Cross-mapped to KSI-MLA-OSM, KSI-CMT-LMC** — same partial-fit
qualifier applies to those.

### 2. `aws.cloudtrail_log_file_validation` → KSI-MLA-OSM

**Moderate:** *"Operate a Security Information and Event Management
(SIEM) or similar system(s) for centralized, tamper-resistent logging."*

**Detector evidences:** CloudTrail log file validation enabled (the
SI-7 / tamper-resistance slice).

**Slice:** Tamper-resistance only. Doesn't evidence SIEM operation,
centralization, alerting, or runtime monitoring. The KSI's full
outcome needs the centralization detector
(`aws.centralized_log_aggregation` from PR #89) plus procedural
runtime evidence.

### 3. `aws.cloudwatch_alarms_critical` → KSI-MLA-OSM

**Moderate:** same SIEM statement as above.

**Detector evidences:** CloudWatch metric alarms on critical metrics.

**Slice:** Alerting only — one component of SIEM operation. Doesn't
evidence centralization, log aggregation, or correlation analysis.

### 4. `aws.guardduty_enabled` → KSI-MLA-OSM

**Moderate:** SIEM statement.

**Detector evidences:** GuardDuty threat-detection enabled.

**Slice:** GuardDuty is threat-detection, SIEM-adjacent. The KSI is
explicitly about a SIEM-or-similar; GuardDuty is closer to "EDR/IDS
feeding the SIEM" than to the SIEM itself. Defensible cross-mapping
via SI-4 controls but partial.

### 5. `aws.elb_access_logs` → KSI-MLA-LET

**Moderate:** *"Maintain a list... that will be logged... then do so."*

**Detector evidences:** ELB access logs configured.

**Slice:** Load-balancer access logs only — narrow surface. Application
logs, database audit logs, OS logs uncovered.

### 6. `aws.vpc_flow_logs_enabled` → KSI-MLA-LET

**Moderate:** same MLA-LET statement.

**Detector evidences:** VPC flow logs configured.

**Slice:** Network-flow events only — covers AU-2 / AU-12 for the
network surface. Same partial-coverage caveat as the other MLA-LET
detectors.

### 7. `aws.fips_ssl_policies_on_lb_listeners` → KSI-SVC-VRI

**Moderate:** *"Use cryptographic methods to validate the integrity
of machine-based information resources."*

**Detector evidences:** Load-balancer listeners use FIPS-compliant SSL
policies.

**Slice:** FIPS SSL is about *cryptographic compliance*, not directly
about *integrity validation*. The KSI's outcome is closer to "verify
resources haven't been tampered with via cryptographic checks" — code
signing, image attestation, file integrity monitoring. FIPS SSL
contributes via SI-7(1) (Integrity Checks) but the semantic match is
weaker than the original mapping suggested.

**Cross-mapped to KSI-SVC-SNT** — that's a closer fit semantically
(SVC-SNT is about securing network traffic; FIPS-compliant TLS does
exactly that). The KSI-SVC-VRI mapping should be downgraded to a
note-only cross-mapping; KSI-SVC-SNT may even be the better primary.

### 8. `aws.access_analyzer_enabled` → KSI-CNA-EIS

**Moderate:** *"Use automated services to persistently assess the
security posture of all machine-based information resources and
automatically enforce their intended operational state."*

**Detector evidences:** IAM Access Analyzer enabled.

**Slice:** Access Analyzer assesses IAM-policy posture (CA-2.1/CA-7.1
review-of-controls). It does NOT "automatically enforce intended
state" — it surfaces findings; humans or other automation respond.
The KSI's full outcome includes automated enforcement, which lives at
the AWS Config + automation-remediation layer.

### 9. `aws.backup_restore_testing` → KSI-RPL-TRC

**Moderate:** *"Persistently test the capability to recover from
incidents and contingencies, including alignment with defined recovery
objectives."*

**Detector evidences:** Backup configuration (and presumably whatever
the detector specifically checks — likely AWS Backup test plans, vault
configurations, or tags signaling test schedules).

**Slice:** The KSI's word is **test** — actually exercising the
recovery capability. IaC can declare the backup configuration that
makes recovery testable but cannot evidence the test having been
performed. That's runtime/operational evidence (last-test timestamp,
RTO measurement) which lives in procedural Manifests or in
AWS-Backup test-plan-execution records.

---

## Reclassification candidates (2)

Each of these is worth maintainer judgment on whether to keep, re-home,
or drop. None are urgent — the detectors still produce useful evidence;
the question is which KSI's coverage roll-up they should land in.

### 1. `aws.iam_user_access_keys` → KSI-IAM-MFA

**Moderate:** *"Enforce multi-factor authentication (MFA) using methods
that are difficult to intercept or impersonate (phishing-resistant MFA)
for all user authentication."*

**Detector evidences:** Long-lived IAM user access keys present (a
finding, not a positive evidence shape).

**Mismatch:** Access keys are *programmatic credentials*, not MFA.
The KSI is specifically about MFA enforcement for user authentication.
A user with a long-lived access key is a finding for...
- KSI-IAM-SNU (Securing Non-User Authentication) — *if* the access key
  is used by automation, OR
- KSI-IAM-AAM (Automating Account Management) — credential lifecycle
  hygiene.

**Recommendation:** Re-home to KSI-IAM-SNU. The current mapping is
defensible only via a generous reading of "factors compromised by
phishing" but the catalog control linkage doesn't support it directly
(IAM-MFA's controls are IA-2 family, while access-key hygiene maps to
IA-5 family).

### 2. `aws.backup_retention_configured` → KSI-RPL-ABO

**Moderate:** *"Persistently review the alignment of machine-based
information resource backups with defined recovery objectives."*

**Detector evidences:** Backup retention period is configured.

**Mismatch:** The KSI's outcome is **review of alignment** — a
procedural cycle that compares backup retention to recovery objectives
(RTO/RPO). The detector evidences the *input* to that review (the
configured retention), not the review itself. The retention number
also doesn't tell us whether it aligns with the customer's RTO/RPO
without the customer's recovery-objective declaration.

**Recommendation:** Keep the mapping but downgrade to partial
cross-mapping with explicit notes — the detector evidences the
configuration that the procedural review needs, not the review
itself. Same shape as the SVC-RUD treatment.

---

## Direct fits — appendix (23)

These mappings are clean. Detector and KSI moderate statement align
strongly enough that no audit-side change is recommended.

| Detector | KSI | Why direct fit |
|---|---|---|
| `aws.config_enabled` | KSI-MLA-EVC | Config evaluates configurations — exactly the moderate statement. |
| `aws.federated_identity_providers` | KSI-IAM-APM | IAM Identity Center / federated SSO is passwordless auth. |
| `aws.iam_admin_policy_usage` | KSI-IAM-ELP | Admin policies violate least privilege; flagging them evidences the discipline. |
| `aws.iam_inline_policies_audit` | KSI-IAM-ELP | Inline policies bypass managed-policy review. |
| `aws.iam_managed_via_terraform` | KSI-IAM-AAM | Terraform-managed IAM IS automated lifecycle.[¹](#footnote-iam-aam) |
| `aws.iam_service_account_keys_age` | KSI-IAM-SNU | Aged keys are insecure for non-user auth. |
| `aws.kms_customer_managed_keys` | KSI-SVC-ASM | CMKs evidence customer-managed key lifecycle. |
| `aws.kms_key_rotation` | KSI-SVC-ASM | Rotation is in the KSI moderate statement verbatim. |
| `aws.mfa_required_on_iam_policies` | KSI-IAM-MFA | Policies requiring MFA for sensitive ops. |
| `aws.nacl_open_egress` | KSI-CNA-RNT | Egress restriction is the KSI outcome. |
| `aws.rds_public_accessibility` | KSI-CNA-RNT | RDS exposure to public internet ↔ traffic restriction. |
| `aws.s3_bucket_public_acl` | KSI-CNA-RNT | S3 public ACLs are network-traffic exposure. |
| `aws.secrets_manager_rotation` | KSI-SVC-ASM | Automated secret rotation matches the KSI. |
| `aws.security_group_open_ingress` | KSI-CNA-RNT | Ingress restriction is the KSI outcome. |
| `aws.suspicious_activity_response` | KSI-IAM-SUS | Automated EventBridge→Lambda IS the KSI outcome. |
| `aws.terraform_inventory` | KSI-PIY-GIV | Authoritative-source automatic inventory.[²](#footnote-piy-giv) |
| `aws.tls_on_lb_listeners` | KSI-SVC-SNT | Encrypted network traffic. |
| `aws.vpc_logical_segmentation` | KSI-CNA-ULN | Logical networking primitives. |
| `aws.ec2_imdsv2_required` | KSI-CNA-IBP | IMDSv2 IS an AWS best practice. |
| `github.action_pinning` | KSI-SCR-MIT | Action pinning is supply-chain mitigation. |
| `github.ci_validation_gates` | KSI-CMT-VTD | CI validation IS the KSI outcome. |
| `github.immutable_deploy_patterns` | KSI-CMT-RMV | Immutable deploys for change management. |
| `github.supply_chain_monitoring` | KSI-SCR-MON | Dependabot / SCA tooling for supply-chain monitoring. |

### Footnotes — direct fits with caveats worth noting in detector READMEs

<a id="footnote-iam-aam"></a>**¹ `aws.iam_managed_via_terraform` → KSI-IAM-AAM:**
direct fit on the *automation-of-lifecycle* axis (Terraform-managed
IAM IS automated lifecycle). Caveat for the detector README: KSI-IAM-AAM's
moderate statement asks for the *entire* account-management lifecycle
including offboarding/cleanup. A `aws_iam_user "ex_employee"` resource
still in `main.tf` is technically Terraform-managed but is the opposite
of automated lifecycle. The detector can't tell. Worth a one-line
"what it does NOT prove" note in
`src/efterlev/detectors/aws/iam_managed_via_terraform/README.md`
covering the stale-resource case; doesn't change the audit row.

<a id="footnote-piy-giv"></a>**² `aws.terraform_inventory` → KSI-PIY-GIV:**
direct fit *when Terraform is the sole provisioning path*. KSI-PIY-GIV's
moderate statement asks for "real-time inventories of all information
resources." If a customer has ClickOps-provisioned resources alongside
Terraform-managed ones (an explicitly-acknowledged ICP-A pattern per
`docs/icp.md`), the detector covers the Terraform slice only — partial,
not direct. Worth either (a) a one-line caveat in the detector README,
or (b) moving this row to the partial cluster with the same note.
Either way, the underlying mapping stays.

---

## Suggested follow-up PRs

In priority order. Each is a small documentary change (mapping.yaml +
README), not a runtime behavior change:

1. **Tighten partial cross-mappings on the 9 partial-fit detectors.**
   Add `coverage: partial` + explicit notes per the SVC-RUD/SVC-VCM
   pattern from PR #83. ~30 minutes per detector; could be batched
   into one PR per KSI cluster (3 PRs: MLA-LET cluster, MLA-OSM
   cluster, individual cases).

2. **Re-home `aws.iam_user_access_keys`** from KSI-IAM-MFA to
   KSI-IAM-SNU (or move to ksis=[] supplementary). Single-detector
   change with test + smoke updates; ~1 hour.

3. **Downgrade `aws.backup_retention_configured` mapping** to partial
   cross-mapping with explicit notes about the procedural-review gap.

The total reclassification surface is small — most detectors are well-mapped.

---

## Why this audit, why now

After PR #82 lands the `varies_by_level` loader fix, the Gap Agent will
see real moderate-level KSI statements for the 5 KSIs that previously
appeared statement-less. That changes the agent's classification
behavior across the catalog. The audit ensures detector-mapping intent
matches the KSI semantics the agent will now read.

Doing this before v0.1.0 publishes is the right time: the launch-blog
"31 of 60 KSIs covered" claim depends on the mappings being honest.
After this audit + the recommended follow-up reclassifications, the
roll-up may shift slightly (SVC-RUD already moved to partial in PR
#83; iam_user_access_keys re-homing changes which KSI is "covered" by
that detector). Updates to README's coverage stanza land alongside
each follow-up.

---

## What this audit does NOT cover

- **Supplementary 800-53-only detectors** (`ksis=[]`). Those 7
  detectors don't map to KSIs by design; the audit doesn't apply.
- **Cross-mappings on KSIs other than the primary.** Many detectors
  cross-map to a second or third KSI via the FRMR `controls` array.
  Those secondary mappings weren't audited individually here; the
  partial-coverage notes from this audit apply transitively to most
  of them.
- **Detector evidence content quality.** This audit asks "does the
  mapping make sense?" not "does the detector emit useful Evidence?"
  The latter is a separate concern handled in the existing fixture
  + smoke tests.
- **Coverage gaps for KSIs with no detector at all.** The 30
  KSI-mapped → 30 covered KSIs accounting is unchanged by this audit.
  Adding new detectors (PRs #88, #89) covers different ground.
