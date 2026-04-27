resource "aws_instance" "legacy" {
  ami           = "ami-0abcdef1234567890"
  instance_type = "t3.micro"

  # IMDSv1 still reachable — the SSRF-against-metadata-service attack
  # vector. Not flagged today; should be flagged.
  metadata_options {
    http_tokens                 = "optional"
    http_put_response_hop_limit = 1
    http_endpoint               = "enabled"
  }

  tags = {
    Name = "legacy"
  }
}

resource "aws_instance" "default_metadata" {
  ami           = "ami-0abcdef1234567890"
  instance_type = "t3.micro"

  # No metadata_options block — AWS default = IMDSv1 + IMDSv2 both reachable.

  tags = {
    Name = "default_metadata"
  }
}
