resource "aws_flow_log" "main" {
  vpc_id               = "vpc-0abc123"
  traffic_type         = "ALL"
  log_destination_type = "s3"
  log_destination      = "arn:aws:s3:::flow-logs-bucket"
}
