resource "aws_iam_user" "ci" {
  name = "ci-deployer"
}

resource "aws_iam_access_key" "ci" {
  user = "ci-deployer"
}
