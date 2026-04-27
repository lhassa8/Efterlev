# aws.terraform_inventory

Aggregates the scanned codebase's Terraform resources into a configuration-
managed inventory summary. Emits exactly **one** Evidence per scan
characterizing the inventory's size and breadth.

KSI-PIY-GIV ("Generating Inventories") asks the customer to *use
authoritative sources to automatically generate real-time inventories of
all information resources*. A Terraform codebase IS such an inventory —
every `resource "aws_*"` block is a tracked component, and the Terraform
state file (updated automatically on `terraform apply`) is the real-time
record of declared infrastructure.

## What it proves

- **CM-8 (System Component Inventory)** — the codebase declares N
  resources, providing the authoritative component list. The customer
  is using IaC as the source of truth for their inventory rather than
  hand-maintaining a spreadsheet.
- **CM-8(1) (Updates During Installation/Removal)** — `terraform apply`
  updates the inventory automatically when components are added or
  removed. The IaC declaration is the source of truth that drives
  those updates.

## What it does NOT prove

- **Runtime-vs-declared drift.** A resource declared but later modified
  in the AWS console is silently divergent. Drift detection is a
  v1.5+ live-state-correlation feature.
- **Multi-repo completeness.** The scan only sees what's in this one
  Terraform tree. Customers with infrastructure split across many
  repos (or split between Terraform and CloudFormation, etc.) need
  per-repo scans to build the full inventory.
- **Inventory review cadence.** FedRAMP requires periodic inventory
  review; the detector confirms the inventory exists, not that it's
  reviewed.
- **Non-Terraform resources.** Resources created via console, CLI, or
  other IaC tools are invisible until they're brought under Terraform.

## KSI mapping

**KSI-PIY-GIV ("Generating Inventories").** FRMR 0.9.43-beta lists
CM-2(2), CM-7(5), CM-8, CM-8(1), CM-12, CM-12(1), CP-2(8) in this
KSI's `controls` array. This detector evidences CM-8 and CM-8(1)
directly. The other controls (allow-listing of authorized software,
information-location tracking, automated tools, alternate-site
inventory) are adjacent and remain candidates for future
detectors / repo-metadata sources.

## Output shape

Exactly one Evidence per scan when ≥1 resource is declared. Empty
codebases produce no evidence — the customer hasn't declared anything
yet, so there's nothing to inventory.

The Evidence is anchored at the first-declared resource's `source_ref`
so the provenance walker has a real on-disk file to resolve. The
content is workspace-scoped, not file-scoped.

## Example

Input (a Terraform tree with 12 S3 buckets, 8 IAM roles, 2 KMS keys, 1 VPC):

Output:

```json
{
  "detector_id": "aws.terraform_inventory",
  "ksis_evidenced": ["KSI-PIY-GIV"],
  "controls_evidenced": ["CM-8", "CM-8(1)"],
  "content": {
    "resource_type": "terraform_inventory",
    "resource_name": "(workspace)",
    "inventory_state": "tracked",
    "total_resources": 23,
    "distinct_resource_types": 4,
    "top_resource_types": [
      {"resource_type": "aws_s3_bucket", "count": 12},
      {"resource_type": "aws_iam_role", "count": 8},
      {"resource_type": "aws_kms_key", "count": 2},
      {"resource_type": "aws_vpc", "count": 1}
    ]
  }
}
```

## Fixtures

- `fixtures/should_match/multi_resource.tf` — workspace with several
  resource types → emits the inventory summary.
- `fixtures/should_not_match/empty.tf` — file with no resources →
  detector emits nothing.
