resource "aws_s3_bucket_acl" "internal_data" {
  bucket = "internal-data"
  acl    = "private"
}
