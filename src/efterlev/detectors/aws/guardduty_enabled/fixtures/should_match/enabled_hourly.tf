resource "aws_guardduty_detector" "main" {
  enable                       = true
  finding_publishing_frequency = "ONE_HOUR"
}
