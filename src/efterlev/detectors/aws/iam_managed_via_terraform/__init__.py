"""IAM-managed-via-Terraform detector. See `detector.py` for registration."""

from __future__ import annotations

from efterlev.detectors.aws.iam_managed_via_terraform.detector import detect

__all__ = ["detect"]
