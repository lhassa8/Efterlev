resource "aws_secretsmanager_secret" "db_password" {
  name = "db-password"
}

resource "aws_secretsmanager_secret_rotation" "db_password" {
  secret_id           = "aws_secretsmanager_secret.db_password.id"
  rotation_lambda_arn = "arn:aws:lambda:us-east-1:123456789012:function:rotate-db-password"

  rotation_rules {
    automatically_after_days = 30
  }
}
