"""Generate primitives — produce FRMR / HTML / (v1) OSCAL output artifacts.

Importing this package triggers `@primitive` registration for every
module below. The Documentation Agent (Phase 3) composes these primitives
with LLM narrative-fill to produce agent-drafted attestations; the same
primitives used standalone produce scanner-only artifacts with no LLM
involvement (DECISIONS 2026-04-21 design call #2).
"""

from __future__ import annotations

from efterlev.primitives.generate.generate_frmr_attestation import (
    GenerateFrmrAttestationInput,
    GenerateFrmrAttestationOutput,
    generate_frmr_attestation,
)
from efterlev.primitives.generate.generate_frmr_skeleton import (
    GenerateFrmrSkeletonInput,
    GenerateFrmrSkeletonOutput,
    generate_frmr_skeleton,
)
from efterlev.primitives.generate.generate_poam_markdown import (
    GeneratePoamMarkdownInput,
    GeneratePoamMarkdownOutput,
    PoamClassificationInput,
    generate_poam_markdown,
)

__all__ = [
    "GenerateFrmrAttestationInput",
    "GenerateFrmrAttestationOutput",
    "GenerateFrmrSkeletonInput",
    "GenerateFrmrSkeletonOutput",
    "GeneratePoamMarkdownInput",
    "GeneratePoamMarkdownOutput",
    "PoamClassificationInput",
    "generate_frmr_attestation",
    "generate_frmr_skeleton",
    "generate_poam_markdown",
]
