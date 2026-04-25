resource "aws_iam_role_policy" "lambda_exec" {
  name = "lambda-exec-inline"
  role = "lambda-exec"
  policy = <<-EOT
    {
      "Version": "2012-10-17",
      "Statement": [
        {"Effect": "Allow", "Action": "logs:PutLogEvents", "Resource": "*"}
      ]
    }
  EOT
}
