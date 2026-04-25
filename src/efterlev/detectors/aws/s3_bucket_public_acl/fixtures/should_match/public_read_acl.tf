resource "aws_s3_bucket_acl" "public_assets" {
  bucket = "public-assets"
  acl    = "public-read"
}
