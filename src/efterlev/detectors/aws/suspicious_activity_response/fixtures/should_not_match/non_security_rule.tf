# EventBridge rules that aren't sourced from security findings — out of
# scope for this detector. The detector should produce no evidence.

resource "aws_cloudwatch_event_rule" "ec2_state_change" {
  name        = "ec2-state-change"
  description = "Fire on EC2 instance state change — operational concern, not security"

  event_pattern = jsonencode({
    source        = ["aws.ec2"]
    "detail-type" = ["EC2 Instance State-change Notification"]
  })
}

resource "aws_cloudwatch_event_target" "ec2_target" {
  rule      = aws_cloudwatch_event_rule.ec2_state_change.name
  target_id = "ops-notifier"
  arn       = "arn:aws:sns:us-east-1:111122223333:ops-pages"
}

resource "aws_cloudwatch_event_rule" "scheduled_lambda" {
  name                = "nightly-cleanup"
  description         = "Schedule, not finding-driven"
  schedule_expression = "cron(0 5 * * ? *)"
}
