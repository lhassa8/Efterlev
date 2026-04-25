# Install-verification smoke fixture for the release-smoke.yml matrix
# (SPEC-09). Minimal Terraform with deliberate compliance gaps so every
# matrix cell's `efterlev scan` produces at least one evidence record,
# proving the install works end-to-end.
#
# Do NOT copy this into a real Terraform codebase. It is deliberately
# non-compliant and intentionally unusable as infrastructure.
#
# See tests/smoke/README.md for the full contract this fixture upholds.

resource "aws_s3_bucket" "smoke_logs" {
  bucket = "efterlev-smoke-fixture-logs"
  # Deliberately missing: server_side_encryption_configuration
  # Expected to trigger: aws.encryption_s3_at_rest (encryption_state=absent)
}

resource "aws_lb_listener" "smoke_http" {
  load_balancer_arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/smoke/deadbeef"
  port              = 80
  protocol          = "HTTP"
  # Deliberately HTTP. Expected to trigger: aws.tls_on_lb_listeners
  default_action {
    type = "forward"
  }
}
