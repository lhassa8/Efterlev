"""FRMR JSON → internal Indicator/Theme types, with optional schema validation.

The loader is strict about the three things the rest of Efterlev depends on:
the `info.version` field (so provenance records can name which FRMR produced
a claim), the `KSI` block's shape (themes with `indicators` dicts), and —
when a schema is passed — JSON Schema draft 2020-12 validation of the whole
file. Everything else in FRMR (FRD definitions, FRR process blocks) is
loaded lazily or not at all at v0; v1 can extend this without breaking
callers that only use KSIs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict

from efterlev.errors import CatalogLoadError
from efterlev.models import Indicator, Theme


class FrmrDocument(BaseModel):
    """Loaded, parsed, and (optionally) schema-validated FRMR documentation."""

    model_config = ConfigDict(frozen=True)

    version: str
    last_updated: str
    themes: dict[str, Theme]
    # Indicators carry per-level statements resolved at load time using the
    # `level` parameter passed to `load_frmr` (default "moderate"). The
    # resolved statement is the level-specific text from
    # `varies_by_level.{level}.statement` if present, otherwise the legacy
    # top-level `statement`. This means an FrmrDocument is **baseline-
    # coupled**: a workspace initialized for `fedramp-20x-moderate` carries
    # moderate-level statements; if v0.2 ever supports concurrent baselines
    # in one process (e.g., low + moderate side-by-side), separate
    # FrmrDocuments must be loaded — the cache cannot be shared.
    indicators: dict[str, Indicator]
    # KSI-CSX-ORD prescribed initial-authorization sequence, resolved at
    # load time from `FRR.KSI.data.20x.CSX.KSI-CSX-ORD.following_information`
    # by matching each entry's parenthetical name (e.g. "Minimum Assessment
    # Scope (MAS)") against the AFR theme's indicator names. Empty list for
    # catalogs that lack a CSX-ORD entry; consumers requesting CSX-ORD
    # output gracefully fall back when the list is empty. Pre-2026-04-29
    # cached FrmrDocument JSON files load with this defaulted to [] —
    # `efterlev poam --sort csx-ord` prints a nudge to re-init when the
    # workspace's cache predates this field.
    csx_ord_sequence: list[str] = []


def load_frmr(
    path: Path,
    *,
    schema_path: Path | None = None,
    level: str = "moderate",
) -> FrmrDocument:
    """Load an FRMR JSON file into the internal model.

    If `schema_path` is given, the document is validated against that JSON
    Schema (draft 2020-12) before parsing; validation failures raise
    `CatalogLoadError` with the first offending path. Without `schema_path`,
    only Pydantic-level structural checks run.

    `level` selects the impact-level statement to load per indicator. FRMR
    v0.9.0-beta moved some indicator statements under
    `varies_by_level.{level}.statement` (5 of 60 KSIs as of catalog
    `0.9.43-beta`); the loader prefers that path and falls back to a
    top-level `statement` for catalogs that haven't migrated. Default
    "moderate" matches the only baseline supported in v0.

    Raises `CatalogLoadError` on I/O, JSON, schema, or structural failure.
    """
    try:
        with path.open() as f:
            raw: dict[str, Any] = json.load(f)
    except OSError as e:
        raise CatalogLoadError(f"failed to read FRMR at {path}: {e}") from e
    except json.JSONDecodeError as e:
        raise CatalogLoadError(f"FRMR at {path} is not valid JSON: {e}") from e

    if schema_path is not None:
        try:
            with schema_path.open() as f:
                schema = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise CatalogLoadError(f"failed to load FRMR schema at {schema_path}: {e}") from e
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(raw))
        if errors:
            first = errors[0]
            at = "/".join(str(p) for p in first.absolute_path) or "(root)"
            raise CatalogLoadError(
                f"FRMR at {path} failed schema validation at {at}: {first.message}"
            )

    try:
        info = raw["info"]
        ksi_block = raw["KSI"]
        version = info["version"]
        last_updated = info["last_updated"]
    except KeyError as e:
        raise CatalogLoadError(f"FRMR at {path} missing required key: {e}") from e

    themes: dict[str, Theme] = {}
    indicators: dict[str, Indicator] = {}

    for theme_id, theme_raw in ksi_block.items():
        themes[theme_id] = Theme(
            id=theme_id,
            name=theme_raw.get("name", theme_id),
            short_name=theme_raw.get("short_name"),
            description=theme_raw.get("theme"),
        )
        for ind_id, ind_raw in theme_raw.get("indicators", {}).items():
            level_stmt = ind_raw.get("varies_by_level", {}).get(level, {}).get("statement")
            statement = level_stmt or ind_raw.get("statement")
            indicators[ind_id] = Indicator(
                id=ind_id,
                theme=theme_id,
                name=ind_raw.get("name", ind_id),
                statement=statement,
                controls=list(ind_raw.get("controls", [])),
                fka=ind_raw.get("fka"),
            )

    csx_ord_sequence = _resolve_csx_ord_sequence(raw, indicators)

    return FrmrDocument(
        version=version,
        last_updated=last_updated,
        themes=themes,
        indicators=indicators,
        csx_ord_sequence=csx_ord_sequence,
    )


def _resolve_csx_ord_sequence(raw: dict[str, Any], indicators: dict[str, Indicator]) -> list[str]:
    # FRMR catalog stores the CSX-ORD prescribed sequence as a list of
    # human-readable phrases like "Minimum Assessment Scope (MAS)" under
    # `FRR.KSI.data.20x.CSX.KSI-CSX-ORD.following_information`. The
    # parenthetical 3-letter codes don't always match the KSI ID's 3-letter
    # suffix (e.g. catalog says "Secure Configuration Guide (RSC)" but the
    # KSI ID is `KSI-AFR-SCG`), so we resolve by matching each phrase's
    # name component against the indicators' `name` field.
    csx_ord = (
        raw.get("FRR", {})
        .get("KSI", {})
        .get("data", {})
        .get("20x", {})
        .get("CSX", {})
        .get("KSI-CSX-ORD", {})
    )
    sequence_phrases = csx_ord.get("following_information", [])
    if not sequence_phrases:
        return []

    # Build a {name -> ksi_id} lookup. Names are unique across the catalog
    # in 0.9.43-beta; if a future revision introduces a name collision, the
    # last-loaded wins (no special handling — drift surfaces in the
    # ordering and is the kind of thing a re-init would catch).
    name_to_id = {ind.name: ind_id for ind_id, ind in indicators.items()}

    resolved: list[str] = []
    for phrase in sequence_phrases:
        # Strip the parenthetical abbreviation: "Foo Bar (XYZ)" -> "Foo Bar".
        name = phrase.rsplit(" (", 1)[0].strip() if "(" in phrase else phrase.strip()
        ksi_id = name_to_id.get(name)
        if ksi_id is not None:
            resolved.append(ksi_id)
        # Phrases that don't resolve are silently skipped — the catalog
        # may use names that differ from the indicator's `name` field by
        # case or punctuation. Better to skip than to invent attribution.
    return resolved
