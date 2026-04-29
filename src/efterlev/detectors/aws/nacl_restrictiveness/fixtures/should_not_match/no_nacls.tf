# No `aws_network_acl` resources here. The detector should emit zero
# Evidence — if no NACLs exist, there's nothing to evaluate at this layer.
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "private" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
}
