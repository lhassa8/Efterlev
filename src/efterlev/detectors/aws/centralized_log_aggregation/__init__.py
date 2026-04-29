"""AWS `centralized_log_aggregation` detector package.

Importing this package registers the detector with the global registry
via the `@detector` decorator in `detector.py`.
"""

from __future__ import annotations

from efterlev.detectors.aws.centralized_log_aggregation import detector  # noqa: F401
