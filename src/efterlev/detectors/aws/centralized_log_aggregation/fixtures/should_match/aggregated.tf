resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/app/api"
  retention_in_days = 90
}

resource "aws_cloudtrail" "audit" {
  name                          = "primary-audit"
  s3_bucket_name                = "audit-trail-bucket"
  enable_log_file_validation    = true
  is_multi_region_trail         = true
  include_global_service_events = true
}

resource "aws_flow_log" "vpc_flow" {
  log_destination = "arn:aws:logs:us-east-1:123456789012:log-group:vpc-flow"
  traffic_type    = "ALL"
  vpc_id          = "vpc-0abc123"
}

resource "aws_securityhub_account" "main" {}

resource "aws_cloudwatch_log_subscription_filter" "to_firehose" {
  name            = "ship-to-firehose"
  log_group_name  = aws_cloudwatch_log_group.app.name
  filter_pattern  = ""
  destination_arn = aws_kinesis_firehose_delivery_stream.siem.arn
  role_arn        = "arn:aws:iam::123456789012:role/log-shipper"
}

resource "aws_kinesis_firehose_delivery_stream" "siem" {
  name        = "siem-ingest"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn   = "arn:aws:iam::123456789012:role/firehose"
    bucket_arn = "arn:aws:s3:::siem-archive"
  }
}
