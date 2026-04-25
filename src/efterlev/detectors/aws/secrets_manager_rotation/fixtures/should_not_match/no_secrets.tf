# No Secrets Manager resources at all — detector emits zero evidence.
resource "aws_s3_bucket" "unrelated" {
  bucket = "no-secrets-here"
}
