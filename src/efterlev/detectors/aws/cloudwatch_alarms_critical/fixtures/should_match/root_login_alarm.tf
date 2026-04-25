resource "aws_cloudwatch_metric_alarm" "root_login" {
  alarm_name          = "root-account-used"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "RootAccountUsageCount"
  namespace           = "CWLogs"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Alarm when root account is used"
  alarm_actions       = ["arn:aws:sns:us-east-1:123456789012:security-alerts"]
}
