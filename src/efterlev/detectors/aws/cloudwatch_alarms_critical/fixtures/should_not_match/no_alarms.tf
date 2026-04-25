# Fixture: an S3 bucket with no CloudWatch alarms declared. The detector
# emits zero evidence against this file.
resource "aws_s3_bucket" "logs" {
  bucket = "nothing-alarmed"
}
