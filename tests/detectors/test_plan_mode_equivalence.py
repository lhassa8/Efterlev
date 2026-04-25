"""Plan-mode vs HCL-mode detector-evidence equivalence tests (Phase B).

Scope at this commit: one detector (`aws.encryption_s3_at_rest`) across
its should_match fixtures. The shape of the assertion is a reusable
helper `_assert_plan_equivalent_to_hcl(...)` so extending coverage to
other detectors later is one test-case per pattern rather than a
per-detector rewrite.

Plan-mode fixtures live alongside their `.tf` siblings as
`<name>.plan.json` — hand-crafted to mirror what `terraform show -json`
produces for the same configuration. Generating against a live
Terraform binary is avoided for CI portability; DECISIONS 2026-04-22
"Design: Terraform Plan JSON support" notes that Terraform CLI is NOT
an Efterlev dependency.

Equivalence criteria:
- Same number of Evidence records emitted.
- Matching `detector_id`, `ksis_evidenced`, `controls_evidenced`.
- Matching `content` dict.
- `source_ref.line_start` / `line_end` are NOT compared — plan JSON
  has no line info by design. `source_ref.file` comparison is also
  skipped (HCL path vs plan-JSON path).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from efterlev.detectors.aws.access_analyzer_enabled.detector import (
    detect as detect_access_analyzer,
)
from efterlev.detectors.aws.backup_retention_configured.detector import (
    detect as detect_backup,
)
from efterlev.detectors.aws.cloudtrail_audit_logging.detector import (
    detect as detect_cloudtrail,
)
from efterlev.detectors.aws.cloudtrail_log_file_validation.detector import (
    detect as detect_cloudtrail_lfv,
)
from efterlev.detectors.aws.cloudwatch_alarms_critical.detector import (
    detect as detect_cw_alarms,
)
from efterlev.detectors.aws.config_enabled.detector import (
    detect as detect_config,
)
from efterlev.detectors.aws.elb_access_logs.detector import (
    detect as detect_elb_logs,
)
from efterlev.detectors.aws.encryption_ebs.detector import detect as detect_ebs
from efterlev.detectors.aws.encryption_s3_at_rest.detector import (
    detect as detect_s3_at_rest,
)
from efterlev.detectors.aws.fips_ssl_policies_on_lb_listeners.detector import (
    detect as detect_fips,
)
from efterlev.detectors.aws.guardduty_enabled.detector import (
    detect as detect_guardduty,
)
from efterlev.detectors.aws.iam_admin_policy_usage.detector import (
    detect as detect_iam_admin,
)
from efterlev.detectors.aws.iam_inline_policies_audit.detector import (
    detect as detect_iam_inline,
)
from efterlev.detectors.aws.iam_password_policy.detector import (
    detect as detect_password,
)
from efterlev.detectors.aws.iam_service_account_keys_age.detector import (
    detect as detect_iam_sa_keys,
)
from efterlev.detectors.aws.iam_user_access_keys.detector import (
    detect as detect_access_keys,
)
from efterlev.detectors.aws.kms_customer_managed_keys.detector import (
    detect as detect_kms_cmks,
)
from efterlev.detectors.aws.kms_key_rotation.detector import (
    detect as detect_kms_rotation,
)
from efterlev.detectors.aws.mfa_required_on_iam_policies.detector import (
    detect as detect_mfa,
)
from efterlev.detectors.aws.nacl_open_egress.detector import (
    detect as detect_nacl_open_egress,
)
from efterlev.detectors.aws.rds_encryption_at_rest.detector import (
    detect as detect_rds,
)
from efterlev.detectors.aws.rds_public_accessibility.detector import (
    detect as detect_rds_public,
)
from efterlev.detectors.aws.s3_bucket_public_acl.detector import (
    detect as detect_s3_public_acl,
)
from efterlev.detectors.aws.s3_public_access_block.detector import (
    detect as detect_pab,
)
from efterlev.detectors.aws.secrets_manager_rotation.detector import (
    detect as detect_secrets_rotation,
)
from efterlev.detectors.aws.security_group_open_ingress.detector import (
    detect as detect_sg_open_ingress,
)
from efterlev.detectors.aws.sns_topic_encryption.detector import (
    detect as detect_sns_enc,
)
from efterlev.detectors.aws.sqs_queue_encryption.detector import (
    detect as detect_sqs_enc,
)
from efterlev.detectors.aws.tls_on_lb_listeners.detector import (
    detect as detect_tls,
)
from efterlev.detectors.aws.vpc_flow_logs_enabled.detector import (
    detect as detect_flow_logs,
)
from efterlev.terraform import parse_plan_json, parse_terraform_file

AWS_DETECTORS_DIR = Path(__file__).resolve().parents[2] / "src" / "efterlev" / "detectors" / "aws"
DETECTOR_DIR = AWS_DETECTORS_DIR / "encryption_s3_at_rest"


def _evidence_comparable(ev: Any) -> dict[str, Any]:
    """Project Evidence to just the fields that should match across modes."""
    return {
        "detector_id": ev.detector_id,
        "ksis_evidenced": sorted(ev.ksis_evidenced),
        "controls_evidenced": sorted(ev.controls_evidenced),
        "content": ev.content,
    }


def _assert_plan_equivalent_to_hcl(
    *,
    tf_path: Path,
    plan_path: Path,
    detect_fn: Any,
) -> None:
    """Run `detect_fn` against both sources; assert evidence matches."""
    hcl_resources = parse_terraform_file(tf_path)
    hcl_evidence = [_evidence_comparable(ev) for ev in detect_fn(hcl_resources)]

    plan_resources = parse_plan_json(plan_path)
    plan_evidence = [_evidence_comparable(ev) for ev in detect_fn(plan_resources)]

    # Sort both by resource_name for stable comparison — order is not part
    # of the equivalence contract; the multiset of records is.
    def _key(e: dict) -> str:
        return str(e["content"].get("resource_name", ""))

    hcl_evidence.sort(key=_key)
    plan_evidence.sort(key=_key)

    assert hcl_evidence == plan_evidence, (
        "Plan-mode evidence diverges from HCL-mode evidence for the same "
        f"configuration.\n  HCL: {hcl_evidence}\n  Plan: {plan_evidence}"
    )


# ---------------------------------------------------------------------------
# encryption_s3_at_rest
# ---------------------------------------------------------------------------


def test_encryption_s3_at_rest_inline_kms_equivalent() -> None:
    _assert_plan_equivalent_to_hcl(
        tf_path=DETECTOR_DIR / "fixtures" / "should_match" / "inline_kms.tf",
        plan_path=DETECTOR_DIR / "fixtures" / "should_match" / "inline_kms.plan.json",
        detect_fn=detect_s3_at_rest,
    )


def test_encryption_s3_at_rest_separate_sse_resource_equivalent() -> None:
    _assert_plan_equivalent_to_hcl(
        tf_path=DETECTOR_DIR / "fixtures" / "should_match" / "separate_sse_resource.tf",
        plan_path=(DETECTOR_DIR / "fixtures" / "should_match" / "separate_sse_resource.plan.json"),
        detect_fn=detect_s3_at_rest,
    )


# ---------------------------------------------------------------------------
# tls_on_lb_listeners
# ---------------------------------------------------------------------------


def test_tls_on_lb_listeners_https_listener_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "tls_on_lb_listeners" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "https_listener.tf",
        plan_path=fx / "https_listener.plan.json",
        detect_fn=detect_tls,
    )


# ---------------------------------------------------------------------------
# backup_retention_configured
# ---------------------------------------------------------------------------


def test_backup_retention_configured_rds_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "backup_retention_configured" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "rds_with_retention.tf",
        plan_path=fx / "rds_with_retention.plan.json",
        detect_fn=detect_backup,
    )


# ---------------------------------------------------------------------------
# mfa_required_on_iam_policies — the detector whose HCL-mode limitation
# (`policy attribute is not a literal JSON string` when jsonencode is used)
# is the motivating case for plan-mode in IAM-heavy codebases. Here we
# validate equivalence on the HCL heredoc case; the plan-mode-unlocks-
# jsonencode case is covered empirically by the 2026-04-22 dogfood.
# ---------------------------------------------------------------------------


def test_mfa_required_on_iam_policies_mfa_gated_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "mfa_required_on_iam_policies" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "mfa_gated_policy.tf",
        plan_path=fx / "mfa_gated_policy.plan.json",
        detect_fn=detect_mfa,
    )


# ---------------------------------------------------------------------------
# Remaining detectors — one representative should_match fixture each.
# ---------------------------------------------------------------------------


def test_cloudtrail_audit_logging_multi_region_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "cloudtrail_audit_logging" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "multi_region_trail.tf",
        plan_path=fx / "multi_region_trail.plan.json",
        detect_fn=detect_cloudtrail,
    )


def test_cloudtrail_log_file_validation_validated_trail_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "cloudtrail_log_file_validation" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "validated_trail.tf",
        plan_path=fx / "validated_trail.plan.json",
        detect_fn=detect_cloudtrail_lfv,
    )


def test_fips_ssl_policies_tls13_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "fips_ssl_policies_on_lb_listeners" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "tls13_policy.tf",
        plan_path=fx / "tls13_policy.plan.json",
        detect_fn=detect_fips,
    )


def test_encryption_ebs_instance_root_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "encryption_ebs" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "instance_encrypted_root.tf",
        plan_path=fx / "instance_encrypted_root.plan.json",
        detect_fn=detect_ebs,
    )


def test_iam_password_policy_strict_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "iam_password_policy" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "strict_policy.tf",
        plan_path=fx / "strict_policy.plan.json",
        detect_fn=detect_password,
    )


def test_iam_user_access_keys_ci_deploy_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "iam_user_access_keys" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "ci_deploy_key.tf",
        plan_path=fx / "ci_deploy_key.plan.json",
        detect_fn=detect_access_keys,
    )


def test_kms_key_rotation_symmetric_rotated_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "kms_key_rotation" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "symmetric_rotated.tf",
        plan_path=fx / "symmetric_rotated.plan.json",
        detect_fn=detect_kms_rotation,
    )


def test_rds_encryption_at_rest_cmk_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "rds_encryption_at_rest" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "encrypted_cmk.tf",
        plan_path=fx / "encrypted_cmk.plan.json",
        detect_fn=detect_rds,
    )


def test_s3_public_access_block_all_flags_true_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "s3_public_access_block" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "all_flags_true.tf",
        plan_path=fx / "all_flags_true.plan.json",
        detect_fn=detect_pab,
    )


def test_vpc_flow_logs_vpc_all_traffic_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "vpc_flow_logs_enabled" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "vpc_all_traffic_s3.tf",
        plan_path=fx / "vpc_all_traffic_s3.plan.json",
        detect_fn=detect_flow_logs,
    )


def test_security_group_open_ingress_ssh_open_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "security_group_open_ingress" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "ssh_open_to_world.tf",
        plan_path=fx / "ssh_open_to_world.plan.json",
        detect_fn=detect_sg_open_ingress,
    )


def test_rds_public_accessibility_public_db_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "rds_public_accessibility" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "public_db.tf",
        plan_path=fx / "public_db.plan.json",
        detect_fn=detect_rds_public,
    )


def test_s3_bucket_public_acl_public_read_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "s3_bucket_public_acl" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "public_read_acl.tf",
        plan_path=fx / "public_read_acl.plan.json",
        detect_fn=detect_s3_public_acl,
    )


def test_nacl_open_egress_wide_open_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "nacl_open_egress" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "wide_open_nacl.tf",
        plan_path=fx / "wide_open_nacl.plan.json",
        detect_fn=detect_nacl_open_egress,
    )


def test_cloudwatch_alarms_root_login_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "cloudwatch_alarms_critical" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "root_login_alarm.tf",
        plan_path=fx / "root_login_alarm.plan.json",
        detect_fn=detect_cw_alarms,
    )


def test_guardduty_enabled_hourly_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "guardduty_enabled" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "enabled_hourly.tf",
        plan_path=fx / "enabled_hourly.plan.json",
        detect_fn=detect_guardduty,
    )


def test_config_enabled_recorder_and_channel_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "config_enabled" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "recorder_and_channel.tf",
        plan_path=fx / "recorder_and_channel.plan.json",
        detect_fn=detect_config,
    )


def test_access_analyzer_account_scoped_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "access_analyzer_enabled" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "account_scoped.tf",
        plan_path=fx / "account_scoped.plan.json",
        detect_fn=detect_access_analyzer,
    )


def test_kms_customer_managed_keys_app_data_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "kms_customer_managed_keys" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "app_data_cmk.tf",
        plan_path=fx / "app_data_cmk.plan.json",
        detect_fn=detect_kms_cmks,
    )


def test_secrets_manager_rotation_db_password_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "secrets_manager_rotation" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "db_password_30_day.tf",
        plan_path=fx / "db_password_30_day.plan.json",
        detect_fn=detect_secrets_rotation,
    )


def test_sns_topic_encryption_cmk_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "sns_topic_encryption" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "cmk_topic.tf",
        plan_path=fx / "cmk_topic.plan.json",
        detect_fn=detect_sns_enc,
    )


def test_sqs_queue_encryption_cmk_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "sqs_queue_encryption" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "cmk_queue.tf",
        plan_path=fx / "cmk_queue.plan.json",
        detect_fn=detect_sqs_enc,
    )


def test_iam_inline_policies_audit_role_inline_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "iam_inline_policies_audit" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "role_inline_policy.tf",
        plan_path=fx / "role_inline_policy.plan.json",
        detect_fn=detect_iam_inline,
    )


def test_iam_admin_policy_usage_admin_role_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "iam_admin_policy_usage" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "admin_role.tf",
        plan_path=fx / "admin_role.plan.json",
        detect_fn=detect_iam_admin,
    )


def test_iam_service_account_keys_ci_user_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "iam_service_account_keys_age" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "ci_user_keys.tf",
        plan_path=fx / "ci_user_keys.plan.json",
        detect_fn=detect_iam_sa_keys,
    )


def test_elb_access_logs_alb_with_logs_equivalent() -> None:
    fx = AWS_DETECTORS_DIR / "elb_access_logs" / "fixtures" / "should_match"
    _assert_plan_equivalent_to_hcl(
        tf_path=fx / "alb_with_access_logs.tf",
        plan_path=fx / "alb_with_access_logs.plan.json",
        detect_fn=detect_elb_logs,
    )
