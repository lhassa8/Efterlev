resource "aws_network_acl" "private_subnet" {
  vpc_id = "vpc-0abc123"

  ingress {
    rule_no     = 100
    rule_action = "allow"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_block  = "10.0.0.0/8"
  }

  ingress {
    rule_no     = 200
    rule_action = "deny"
    protocol    = "-1"
    from_port   = 0
    to_port     = 65535
    cidr_block  = "0.0.0.0/0"
  }

  egress {
    rule_no     = 100
    rule_action = "allow"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_block  = "0.0.0.0/0"
  }
}
