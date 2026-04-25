# No access analyzer resource declared — detector emits zero evidence.
resource "aws_s3_bucket" "unrelated" {
  bucket = "nothing-to-analyze"
}
