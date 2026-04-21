"""NIST 800-53 Rev 5 catalog → flattened `Control` / `ControlEnhancement` dicts.

Trestle's OSCAL Catalog walks `groups → controls → nested controls`. Nested
controls are enhancements (e.g., SC-28(1) under SC-28). This loader
flattens the tree into two lookup dicts:

  controls           keyed by top-level control id (e.g. "sc-28"), carrying
                     its enhancements inline in a Control.enhancements list
  enhancements_by_id keyed by enhancement id (e.g. "sc-28.1"), pointing at
                     the ControlEnhancement directly

Ids follow OSCAL's lowercase-hyphenated convention, which matches FRMR's
`controls` field convention exactly — so KSI→control cross-lookups work
without case-folding or normalization.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from trestle.oscal.catalog import Catalog as TrestleCatalog

from efterlev.errors import CatalogLoadError
from efterlev.models import Control, ControlEnhancement


class OscalCatalog(BaseModel):
    """Flattened lookup view of a loaded NIST 800-53 OSCAL catalog."""

    model_config = ConfigDict(frozen=True)

    controls: dict[str, Control]
    enhancements_by_id: dict[str, ControlEnhancement]

    def lookup(self, control_id: str) -> Control | ControlEnhancement | None:
        """Return the Control (top-level) or ControlEnhancement matching `control_id`, or None."""
        return self.controls.get(control_id) or self.enhancements_by_id.get(control_id)


def load_oscal_800_53(path: Path) -> OscalCatalog:
    """Load a NIST 800-53 Rev 5 OSCAL catalog file and flatten it.

    Results are cached in-process by resolved path + mtime so repeat loads
    (common across agents / tests in a single process) don't pay trestle's
    ~28s parse more than once. If the underlying file is rewritten, the
    cache naturally invalidates because mtime changes.

    Raises `CatalogLoadError` on I/O, parsing, or structural failure.
    """
    if not path.exists():
        raise CatalogLoadError(f"failed to load OSCAL catalog at {path}: file not found")
    return _load_oscal_800_53_cached(str(path.resolve()), path.stat().st_mtime_ns)


@lru_cache(maxsize=8)
def _load_oscal_800_53_cached(resolved_path: str, mtime_ns: int) -> OscalCatalog:
    """Inner cached load; keyed by (resolved path, mtime) so file changes invalidate."""
    path = Path(resolved_path)
    try:
        trestle_catalog = TrestleCatalog.oscal_read(path)
    except Exception as e:  # trestle raises a zoo of exceptions; we wrap them
        raise CatalogLoadError(f"failed to load OSCAL catalog at {path}: {e}") from e
    if trestle_catalog is None:
        raise CatalogLoadError(f"failed to load OSCAL catalog at {path}: parse returned None")

    controls: dict[str, Control] = {}
    enhancements: dict[str, ControlEnhancement] = {}

    for group in trestle_catalog.groups or []:
        for ctrl in group.controls or []:
            family = ctrl.id.split("-", 1)[0] if "-" in ctrl.id else ctrl.id
            enh_list: list[ControlEnhancement] = []
            for sub in ctrl.controls or []:
                enh = ControlEnhancement(
                    id=sub.id,
                    parent_id=ctrl.id,
                    title=sub.title or sub.id,
                )
                enh_list.append(enh)
                enhancements[sub.id] = enh
            controls[ctrl.id] = Control(
                id=ctrl.id,
                family=family,
                title=ctrl.title or ctrl.id,
                enhancements=enh_list,
            )

    return OscalCatalog(controls=controls, enhancements_by_id=enhancements)
