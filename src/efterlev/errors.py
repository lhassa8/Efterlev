"""Typed exception hierarchy for Efterlev.

Every raise from library code uses one of these types. Never `raise Exception` —
an unexpected bare exception crossing a primitive or agent boundary is a bug, not
an error mode users should see. The CLI catches `EfterlevError` at the top level
and formats it for the terminal; anything else is a traceback.
"""

from __future__ import annotations


class EfterlevError(Exception):
    """Base class for every exception raised by Efterlev's own code paths."""


class CatalogLoadError(EfterlevError):
    """A vendored catalog (FRMR, NIST 800-53) failed to load, parse, or validate."""


class ConfigError(EfterlevError):
    """`.efterlev/config.toml` is malformed, missing, or references an unknown baseline."""


class DetectorError(EfterlevError):
    """A detector raised while scanning source material, or failed to load its mapping."""


class PrimitiveError(EfterlevError):
    """A primitive's input or output failed its typed contract."""


class AgentError(EfterlevError):
    """An agent failed to produce a valid typed artifact (e.g. malformed LLM response)."""


class ProvenanceError(EfterlevError):
    """The provenance store rejected a write, or a walk failed to resolve a record."""


class ValidationError(EfterlevError):
    """An output artifact (FRMR, OSCAL) failed schema validation before return."""
