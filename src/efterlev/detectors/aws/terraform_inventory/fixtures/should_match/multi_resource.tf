resource "aws_s3_bucket" "logs" {
  bucket = "logs"
}

resource "aws_s3_bucket" "data" {
  bucket = "data"
}

resource "aws_s3_bucket" "backups" {
  bucket = "backups"
}

resource "aws_iam_role" "app" {
  name = "app"
}

resource "aws_iam_role" "deploy" {
  name = "deploy"
}

resource "aws_kms_key" "primary" {
  description = "primary"
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
