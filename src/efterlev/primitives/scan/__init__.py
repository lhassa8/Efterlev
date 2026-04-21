"""Scan primitives — parse source material and run detectors.

Importing this package also imports the scan primitive modules below, which
trigger `@primitive` registration and (transitively) `@detector`
registration via `efterlev.detectors`.
"""

from __future__ import annotations

from efterlev.primitives.scan.scan_terraform import (
    ScanTerraformInput,
    ScanTerraformOutput,
    scan_terraform,
)

__all__ = ["ScanTerraformInput", "ScanTerraformOutput", "scan_terraform"]
