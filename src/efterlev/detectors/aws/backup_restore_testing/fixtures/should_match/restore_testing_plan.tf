resource "aws_backup_restore_testing_plan" "monthly" {
  name                         = "monthly_restore_test"
  schedule_expression          = "cron(0 5 1 * ? *)"
  schedule_expression_timezone = "UTC"
  start_window_hours           = 24

  recovery_point_selection {
    algorithm             = "LATEST_WITHIN_WINDOW"
    include_vaults        = ["arn:aws:backup:us-east-1:111122223333:backup-vault:prod"]
    recovery_point_types  = ["CONTINUOUS", "SNAPSHOT"]
    selection_window_days = 7
  }
}

resource "aws_backup_restore_testing_selection" "monthly_rds" {
  name                      = "monthly_rds_selection"
  restore_testing_plan_id   = aws_backup_restore_testing_plan.monthly.id
  iam_role_arn              = "arn:aws:iam::111122223333:role/RestoreTestingRole"
  protected_resource_type   = "RDS"
  protected_resource_arns   = ["*"]
}
