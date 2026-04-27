resource "aws_iam_role" "app" {
  name = "app"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = []
  })
}

resource "aws_iam_role" "deploy" {
  name = "deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = []
  })
}

resource "aws_iam_policy" "app" {
  name   = "app-permissions"
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = []
  })
}

resource "aws_iam_user" "service_account" {
  name = "ci-runner"
}

resource "aws_iam_role_policy_attachment" "app_to_app" {
  role       = aws_iam_role.app.name
  policy_arn = aws_iam_policy.app.arn
}
