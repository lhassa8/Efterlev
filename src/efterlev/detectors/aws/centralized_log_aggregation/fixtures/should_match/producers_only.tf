resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/app/api"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/handler"
  retention_in_days = 30
}

resource "aws_cloudtrail" "audit" {
  name           = "primary-audit"
  s3_bucket_name = "audit-trail-bucket"
}
