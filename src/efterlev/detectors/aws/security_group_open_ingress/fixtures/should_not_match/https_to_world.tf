resource "aws_security_group" "web" {
  name        = "web-public"
  description = "Public web — HTTPS to world is intentional"
  vpc_id      = "vpc-0abc123"

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
