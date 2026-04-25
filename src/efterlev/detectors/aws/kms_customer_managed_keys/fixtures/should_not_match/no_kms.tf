# No CMK declared — only an S3 bucket using AWS-managed encryption.
resource "aws_s3_bucket" "default_encrypted" {
  bucket = "default-managed-key"
}
