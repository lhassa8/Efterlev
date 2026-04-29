resource "aws_securityhub_account" "main" {}

resource "aws_securityhub_finding_aggregator" "main" {
  linking_mode = "ALL_REGIONS"
}

resource "aws_opensearch_domain" "siem" {
  domain_name = "siem-search"
}
