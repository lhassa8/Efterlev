"""Terraform inventory detector. See `detector.py` for the registration."""

from __future__ import annotations

from efterlev.detectors.aws.terraform_inventory.detector import detect

__all__ = ["detect"]
