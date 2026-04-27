resource "aws_s3_bucket_lifecycle_configuration" "cold_storage" {
  bucket = aws_s3_bucket.archive.id

  rule {
    id     = "to_ia"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }

  rule {
    id     = "to_glacier"
    status = "Enabled"

    transition {
      days          = 180
      storage_class = "GLACIER"
    }
  }
}
