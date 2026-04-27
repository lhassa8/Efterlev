# A typical "backup but no restore-testing" shape: backup vault, plan,
# and selection all exist, but no aws_backup_restore_testing_plan does.
# KSI-RPL-ABO is fine; KSI-RPL-TRC has no IaC evidence here.

resource "aws_backup_vault" "prod" {
  name = "prod"
}

resource "aws_backup_plan" "daily" {
  name = "daily_backups"

  rule {
    rule_name         = "daily"
    target_vault_name = aws_backup_vault.prod.name
    schedule          = "cron(0 5 * * ? *)"

    lifecycle {
      delete_after = 30
    }
  }
}

resource "aws_backup_selection" "daily_rds" {
  name         = "daily_rds_selection"
  plan_id      = aws_backup_plan.daily.id
  iam_role_arn = "arn:aws:iam::111122223333:role/BackupRole"
  resources    = ["*"]
}
