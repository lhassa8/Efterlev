# Empty Terraform file — no resource declarations.
# The terraform_inventory detector emits nothing when there are zero
# resources to inventory; the workspace simply has no infrastructure
# declared yet.

variable "region" {
  default = "us-east-1"
}
