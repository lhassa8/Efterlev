"""High-level `.efterlev/` workspace operations.

Used by `efterlev init` to bootstrap a workspace: verify the vendored
catalog bytes match the pinned SHA-256s, load FRMR and 800-53 into the
internal model, write `.efterlev/config.toml`, cache the parsed catalogs
so later scans skip trestle's ~28s parse, and record a provenance "load
receipt" row so the init itself shows up when someone walks the chain.

Phase 2c's `scan_terraform` will load the cached catalogs from
`.efterlev/cache/` instead of re-parsing trestle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from efterlev.config import BaselineConfig, Config, LLMConfig, save_config
from efterlev.errors import ConfigError
from efterlev.frmr import load_frmr
from efterlev.oscal import load_oscal_800_53
from efterlev.paths import vendored_catalogs_dir, verify_catalog_hashes
from efterlev.provenance import ProvenanceStore

SUPPORTED_BASELINES = {"fedramp-20x-moderate"}


@dataclass(frozen=True)
class InitResult:
    """Summary returned from a successful `init_workspace` call."""

    target: Path
    efterlev_dir: Path
    baseline: str
    frmr_version: str
    frmr_last_updated: str
    num_indicators: int
    num_themes: int
    num_controls: int
    num_enhancements: int
    receipt_record_id: str


def init_workspace(
    target: Path,
    baseline: str,
    *,
    force: bool = False,
    llm_config: LLMConfig | None = None,
) -> InitResult:
    """Create `.efterlev/` under `target`, verify + load catalogs, persist a load receipt.

    Args:
        target: Repo path to initialize.
        baseline: FRMR baseline name; must be in SUPPORTED_BASELINES.
        force: Overwrite an existing `.efterlev/` directory if present.
        llm_config: Optional pre-built LLMConfig. If None, the default
            (anthropic backend) is used. The CLI passes an explicit LLMConfig
            when the user invokes `--llm-backend bedrock` etc.

    Raises:
        ConfigError: baseline not supported, or `.efterlev/` already exists and
            `force=False`.
        CatalogLoadError: vendored catalogs cannot be located or their SHA-256
            does not match the pinned expectations (see paths.EXPECTED_HASHES).
    """
    if baseline not in SUPPORTED_BASELINES:
        raise ConfigError(
            f"baseline {baseline!r} is not supported at v0. "
            f"Supported: {sorted(SUPPORTED_BASELINES)}."
        )

    efterlev_dir = target / ".efterlev"
    if efterlev_dir.exists() and not force:
        raise ConfigError(f"{efterlev_dir} already exists. Re-run with --force to overwrite.")

    catalogs_dir = vendored_catalogs_dir()
    verify_catalog_hashes(catalogs_dir)

    frmr_doc = load_frmr(
        catalogs_dir / "frmr" / "FRMR.documentation.json",
        schema_path=catalogs_dir / "frmr" / "FedRAMP.schema.json",
    )
    oscal_cat = load_oscal_800_53(catalogs_dir / "nist" / "NIST_SP-800-53_rev5_catalog.json")

    efterlev_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = efterlev_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "frmr_document.json").write_text(frmr_doc.model_dump_json(), encoding="utf-8")
    (cache_dir / "oscal_catalog.json").write_text(oscal_cat.model_dump_json(), encoding="utf-8")

    save_config(
        Config(
            baseline=BaselineConfig(id=baseline),
            llm=llm_config if llm_config is not None else LLMConfig(),
        ),
        efterlev_dir / "config.toml",
    )

    with ProvenanceStore(target) as store:
        receipt = store.write_record(
            payload={
                "action": "catalogs_loaded",
                "baseline": baseline,
                "frmr": {
                    "version": frmr_doc.version,
                    "last_updated": frmr_doc.last_updated,
                    "themes": len(frmr_doc.themes),
                    "indicators": len(frmr_doc.indicators),
                },
                "oscal_800_53": {
                    "controls_top_level": len(oscal_cat.controls),
                    "enhancements": len(oscal_cat.enhancements_by_id),
                },
            },
            record_type="evidence",
            primitive="efterlev.init@0.1.0",
            metadata={"source": "init"},
        )

    return InitResult(
        target=target,
        efterlev_dir=efterlev_dir,
        baseline=baseline,
        frmr_version=frmr_doc.version,
        frmr_last_updated=frmr_doc.last_updated,
        num_indicators=len(frmr_doc.indicators),
        num_themes=len(frmr_doc.themes),
        num_controls=len(oscal_cat.controls),
        num_enhancements=len(oscal_cat.enhancements_by_id),
        receipt_record_id=receipt.record_id,
    )
