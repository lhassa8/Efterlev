# Queue with neither SSE-KMS nor SSE-SQS — encryption is absent.
resource "aws_sqs_queue" "plaintext" {
  name = "plaintext-queue"
}
