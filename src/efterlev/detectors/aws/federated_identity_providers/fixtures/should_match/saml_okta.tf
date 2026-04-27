resource "aws_iam_saml_provider" "okta" {
  name                   = "Okta"
  saml_metadata_document = file("${path.module}/okta_metadata.xml")
}
