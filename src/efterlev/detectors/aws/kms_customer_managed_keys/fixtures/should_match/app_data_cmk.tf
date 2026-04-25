resource "aws_kms_key" "app_data" {
  description             = "Application data encryption key"
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 30
  is_enabled              = true
}
