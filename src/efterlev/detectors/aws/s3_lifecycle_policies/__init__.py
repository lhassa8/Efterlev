"""S3 lifecycle-policies detector. See `detector.py` for the registration."""

from __future__ import annotations

from efterlev.detectors.aws.s3_lifecycle_policies.detector import detect

__all__ = ["detect"]
