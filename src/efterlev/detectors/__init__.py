"""Detector library.

Importing this package registers every detector in the library with the
global registry via the `@detector` decorator. The `scan_terraform`
primitive imports this module explicitly so the registry is populated
before it enumerates detectors at scan time.

Each detector is a self-contained folder at
`src/efterlev/detectors/<cloud>/<capability>/` with five files per the
contract in `CONTRIBUTING.md`. Adding a new detector means creating that
folder and adding one import line below.
"""

from __future__ import annotations

# Detector registrations. Each import triggers the @detector decorator
# that registers the detector with the module-level _REGISTRY.
from efterlev.detectors.aws import (
    backup_retention_configured,  # noqa: F401
    cloudtrail_audit_logging,  # noqa: F401
    encryption_s3_at_rest,  # noqa: F401
    fips_ssl_policies_on_lb_listeners,  # noqa: F401
    mfa_required_on_iam_policies,  # noqa: F401
    tls_on_lb_listeners,  # noqa: F401
)
