resource "aws_iam_role_policy_attachment" "break_glass" {
  role       = "break-glass"
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
