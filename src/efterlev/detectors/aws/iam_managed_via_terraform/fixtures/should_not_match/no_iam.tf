resource "aws_s3_bucket" "logs" {
  bucket = "logs"
}

resource "aws_kms_key" "primary" {
  description = "primary"
}

# No `aws_iam_*` resources — the detector emits nothing.
