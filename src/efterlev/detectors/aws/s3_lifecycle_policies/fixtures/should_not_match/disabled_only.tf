resource "aws_s3_bucket_lifecycle_configuration" "placeholder" {
  bucket = aws_s3_bucket.draft.id

  rule {
    id     = "draft_rule"
    status = "Disabled"

    expiration {
      days = 30
    }
  }
}
