resource "aws_security_group" "bastion" {
  name        = "bastion"
  description = "Bastion host with corporate-VPN-only SSH"
  vpc_id      = "vpc-0abc123"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }
}
