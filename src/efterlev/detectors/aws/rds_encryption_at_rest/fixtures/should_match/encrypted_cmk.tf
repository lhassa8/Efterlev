resource "aws_db_instance" "primary" {
  identifier        = "app-primary"
  engine            = "postgres"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_encrypted = true
  kms_key_id        = "arn:aws:kms:us-east-1:123:key/abc-123"
}
