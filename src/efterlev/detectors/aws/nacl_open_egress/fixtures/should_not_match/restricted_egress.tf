resource "aws_network_acl" "private_subnet" {
  vpc_id = "vpc-0abc123"

  egress {
    rule_no     = 100
    rule_action = "allow"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_block  = "0.0.0.0/0"
  }
}
