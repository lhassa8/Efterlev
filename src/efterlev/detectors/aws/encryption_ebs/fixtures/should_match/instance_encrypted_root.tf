resource "aws_instance" "app" {
  ami           = "ami-abc123"
  instance_type = "t3.micro"

  root_block_device {
    volume_size = 20
    encrypted   = true
    kms_key_id  = "arn:aws:kms:us-east-1:123:key/abc-123"
  }
}
