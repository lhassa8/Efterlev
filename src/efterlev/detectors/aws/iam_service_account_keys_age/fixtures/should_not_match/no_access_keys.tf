# IAM user without an aws_iam_access_key — detector emits nothing.
resource "aws_iam_user" "team_member" {
  name = "team-member"
}
