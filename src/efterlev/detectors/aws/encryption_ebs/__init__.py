"""AWS EBS at-rest encryption detector package.

Importing this package registers the detector with the global registry via
the `@detector` decorator in `detector.py`.
"""

from __future__ import annotations

from efterlev.detectors.aws.encryption_ebs import detector  # noqa: F401
