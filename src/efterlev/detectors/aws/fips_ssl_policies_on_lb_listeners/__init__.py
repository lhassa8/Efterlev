"""AWS FIPS-approved ssl_policy detector package.

Importing this package registers the detector with the global registry via
the `@detector` decorator in `detector.py`.
"""

from __future__ import annotations

from efterlev.detectors.aws.fips_ssl_policies_on_lb_listeners import detector  # noqa: F401
