# Role with a scoped managed policy — not AdministratorAccess.
resource "aws_iam_role_policy_attachment" "lambda_exec" {
  role       = "lambda-exec"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
