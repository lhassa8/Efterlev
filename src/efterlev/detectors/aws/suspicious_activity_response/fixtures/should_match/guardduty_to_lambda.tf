resource "aws_cloudwatch_event_rule" "guardduty_findings" {
  name        = "guardduty-findings"
  description = "Fire on GuardDuty findings; route to auto-disable Lambda"

  event_pattern = jsonencode({
    source        = ["aws.guardduty"]
    "detail-type" = ["GuardDuty Finding"]
    detail = {
      severity = [{ "numeric" : [">=", 7] }]
    }
  })
}

resource "aws_cloudwatch_event_target" "guardduty_lambda" {
  rule      = aws_cloudwatch_event_rule.guardduty_findings.name
  target_id = "auto-disable"
  arn       = "arn:aws:lambda:us-east-1:111122223333:function:auto-disable-iam-user"
}
