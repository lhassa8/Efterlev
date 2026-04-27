resource "aws_s3_bucket_lifecycle_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit.id

  rule {
    id     = "expire_after_year"
    status = "Enabled"

    expiration {
      days = 365
    }
  }

  rule {
    id     = "transition_to_glacier"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}
