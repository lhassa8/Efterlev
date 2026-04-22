"""AWS RDS at-rest encryption detector package.

Importing this package registers the detector with the global registry via
the `@detector` decorator in `detector.py`.
"""

from __future__ import annotations

from efterlev.detectors.aws.rds_encryption_at_rest import detector  # noqa: F401
