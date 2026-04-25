# Detectors reference

Stub for SPEC-38.13. Auto-generation from each detector's README + mapping.yaml is queued for a follow-up batch.

Efterlev v0.1.0 ships **30 AWS-Terraform detectors** across these families:

**Encryption at rest (SC-28).** `aws.encryption_s3_at_rest`, `aws.encryption_ebs`, `aws.rds_encryption_at_rest`, `aws.sns_topic_encryption`, `aws.sqs_queue_encryption`. SC-28 is unmapped in FRMR 0.9.43-beta — these detectors carry `ksis=[]` per the established precedent.

**Network boundary (SC-7, KSI-CNA-RNT, KSI-CNA-MAT).** `aws.security_group_open_ingress`, `aws.rds_public_accessibility`, `aws.s3_bucket_public_acl`, `aws.nacl_open_egress`, `aws.s3_public_access_block`, `aws.tls_on_lb_listeners`, `aws.fips_ssl_policies_on_lb_listeners`.

**Monitoring & alerting (SI-4, AU-2, KSI-MLA-OSM, KSI-MLA-LET).** `aws.cloudwatch_alarms_critical`, `aws.guardduty_enabled`, `aws.config_enabled`, `aws.access_analyzer_enabled`, `aws.cloudtrail_audit_logging`, `aws.cloudtrail_log_file_validation`, `aws.vpc_flow_logs_enabled`, `aws.elb_access_logs`.

**Key management (SC-12, KSI-SVC-ASM).** `aws.kms_customer_managed_keys`, `aws.kms_key_rotation`, `aws.secrets_manager_rotation`.

**IAM (IA-2, AC-6, IA-5, KSI-IAM-MFA, KSI-IAM-ELP, KSI-IAM-SNU).** `aws.mfa_required_on_iam_policies`, `aws.iam_password_policy`, `aws.iam_user_access_keys`, `aws.iam_inline_policies_audit`, `aws.iam_admin_policy_usage`, `aws.iam_service_account_keys_age`.

**Backups (CP-9, KSI-RPL-ABO).** `aws.backup_retention_configured`.

Each detector lives at `src/efterlev/detectors/aws/<capability>/` with `detector.py`, `mapping.yaml`, `evidence.yaml`, `fixtures/`, and `README.md`. Read the README to learn what each detector proves and what it does NOT prove.

KSI coverage spans 9 of 11 FRMR-Moderate themes. The two themes not covered (AFR — Authorized Federal Reporting; KSO — Knowing Service Operation) are predominantly procedural and need Evidence Manifests rather than IaC scanning.
