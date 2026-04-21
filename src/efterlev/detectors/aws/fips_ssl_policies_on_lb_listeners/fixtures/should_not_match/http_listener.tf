# HTTP listeners have no ssl_policy to evaluate; this detector skips them entirely
# (aws.tls_on_lb_listeners covers the "should this be TLS at all?" question).
resource "aws_lb_listener" "http" {
  load_balancer_arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/example/abc"
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/app/abc"
  }
}
