# SNS topic without explicit kms_master_key_id — falls back to
# AWS-managed default encryption. The detector emits evidence with
# encryption_state="aws_managed_default" (this isn't a finding, but
# a CMK is the stronger pattern).
resource "aws_sns_topic" "default_encrypted" {
  name = "default-encrypted"
}
