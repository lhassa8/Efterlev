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
    indicators: dict[str, Indicator]


def load_frmr(path: Path, *, schema_path: Path | None = None) -> FrmrDocument:
    """Load an FRMR JSON file into the internal model.

    If `schema_path` is given, the document is validated against that JSON
    Schema (draft 2020-12) before parsing; validation failures raise
    `CatalogLoadError` with the first offending path. Without `schema_path`,
    only Pydantic-level structural checks run.

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
            indicators[ind_id] = Indicator(
                id=ind_id,
                theme=theme_id,
                name=ind_raw.get("name", ind_id),
                statement=ind_raw.get("statement"),
                controls=list(ind_raw.get("controls", [])),
                fka=ind_raw.get("fka"),
            )

    return FrmrDocument(
        version=version,
        last_updated=last_updated,
        themes=themes,
        indicators=indicators,
    )
