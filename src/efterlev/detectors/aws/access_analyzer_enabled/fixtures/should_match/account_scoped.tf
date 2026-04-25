resource "aws_accessanalyzer_analyzer" "default" {
  analyzer_name = "default-account-analyzer"
  type          = "ACCOUNT"
}
