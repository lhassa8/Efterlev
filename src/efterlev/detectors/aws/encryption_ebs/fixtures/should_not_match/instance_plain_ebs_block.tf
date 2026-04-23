resource "aws_instance" "legacy" {
  ami           = "ami-legacy"
  instance_type = "t2.small"

  root_block_device {
    volume_size = 30
    encrypted   = true
  }

  ebs_block_device {
    device_name = "/dev/sdb"
    volume_size = 100
    encrypted   = false
  }
}
