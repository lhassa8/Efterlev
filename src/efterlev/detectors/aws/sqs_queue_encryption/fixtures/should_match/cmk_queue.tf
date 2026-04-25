resource "aws_sqs_queue" "tasks" {
  name              = "task-queue"
  kms_master_key_id = "arn:aws:kms:us-east-1:123456789012:key/abcd1234-abcd-1234-abcd-123456789012"
}
