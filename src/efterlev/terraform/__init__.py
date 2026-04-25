"""Terraform / OpenTofu source parsing.

v0 input modality. Detectors iterate over `TerraformResource` objects the
parser emits; the parser itself does not know about detectors or KSIs — it
just translates `.tf` files into typed resource records with line-accurate
`SourceRef`s so downstream Evidence can cite specific lines.
"""

from __future__ import annotations

from efterlev.terraform.parser import (
    ParseFailure,
    TerraformParseResult,
    parse_terraform_file,
    parse_terraform_tree,
)
from efterlev.terraform.plan import parse_plan_json

__all__ = [
    "ParseFailure",
    "TerraformParseResult",
    "parse_plan_json",
    "parse_terraform_file",
    "parse_terraform_tree",
]
