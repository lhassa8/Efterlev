resource "aws_network_acl" "public_subnet" {
  vpc_id = "vpc-0abc123"

  egress {
    rule_no    = 100
    rule_action = "allow"
    protocol   = "-1"
    from_port  = 0
    to_port    = 0
    cidr_block = "0.0.0.0/0"
  }
}
