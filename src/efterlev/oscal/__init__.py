"""OSCAL input loader — parses the NIST 800-53 Rev 5 catalog via trestle.

v0 uses OSCAL for *input* only: loading the vendored NIST SP 800-53 Rev 5
catalog into our internal `Control` / `ControlEnhancement` types so KSI
mappings can be cross-referenced at load time. OSCAL *output* generators
(Assessment Results, partial SSP, POA&M for Rev5 transition submissions)
are a v1 deliverable per `DECISIONS.md`.
"""

from __future__ import annotations

from efterlev.oscal.loader import OscalCatalog, load_oscal_800_53

__all__ = ["OscalCatalog", "load_oscal_800_53"]
