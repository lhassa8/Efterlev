# ALB with no access_logs block — emits evidence with log_state="absent".
# (Detector still emits Evidence; "should_not_match" here means
# "should not pass the access-logs criterion". The Gap Agent renders.)
resource "aws_lb" "no_logs" {
  name               = "no-logs"
  internal           = false
  load_balancer_type = "application"
  subnets            = ["subnet-abc"]
}
