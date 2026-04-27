resource "aws_instance" "app" {
  ami           = "ami-0abcdef1234567890"
  instance_type = "t3.micro"

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    http_endpoint               = "enabled"
  }

  tags = {
    Name = "app"
  }
}

resource "aws_launch_template" "worker" {
  name_prefix   = "worker-"
  image_id      = "ami-0abcdef1234567890"
  instance_type = "t3.medium"

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    http_endpoint               = "enabled"
  }
}
