resource "aws_vpc" "isolated" {
  cidr_block = "10.10.0.0/16"
}

resource "aws_subnet" "private_a" {
  vpc_id     = aws_vpc.isolated.id
  cidr_block = "10.10.1.0/24"
}

resource "aws_subnet" "private_b" {
  vpc_id     = aws_vpc.isolated.id
  cidr_block = "10.10.2.0/24"
}
