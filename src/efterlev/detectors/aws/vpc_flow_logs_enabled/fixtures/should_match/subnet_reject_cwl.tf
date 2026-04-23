resource "aws_flow_log" "subnet_reject" {
  subnet_id       = "subnet-0def456"
  traffic_type    = "REJECT"
  log_destination = "arn:aws:logs:us-east-1:123:log-group:flow-logs"
}
