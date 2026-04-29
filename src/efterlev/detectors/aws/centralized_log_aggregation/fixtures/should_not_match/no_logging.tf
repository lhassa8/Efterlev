# A workspace with no log producers and no aggregators. The detector
# should emit zero Evidence — KSI-MLA-OSM may be evidence_layer_inapplicable
# for this workspace (or, more likely, the customer has logs/aggregation
# in a separate Terraform tree).
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_s3_bucket" "data" {
  bucket = "my-app-data"
}
