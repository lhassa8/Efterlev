# Managed-policy attachment, NOT an inline policy. Detector emits nothing.
resource "aws_iam_role_policy_attachment" "lambda_managed" {
  role       = "lambda-exec"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
