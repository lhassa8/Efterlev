resource "aws_lb" "main" {
  name               = "main-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = ["subnet-abc"]

  access_logs {
    enabled = true
    bucket  = "my-alb-access-logs"
    prefix  = "main"
  }
}
