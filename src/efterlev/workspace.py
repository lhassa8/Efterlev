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

from dataclasses import dataclass, field
from pathlib import Path

from efterlev.config import BaselineConfig, Config, LLMConfig, save_config
from efterlev.errors import ConfigError
from efterlev.frmr import load_frmr
from efterlev.frmr.freshness import check_catalog_freshness
from efterlev.oscal import load_oscal_800_53
from efterlev.paths import vendored_catalogs_dir, verify_catalog_hashes
from efterlev.provenance import ProvenanceStore

SUPPORTED_BASELINES = {"fedramp-20x-moderate"}

# Maps each supported baseline to the FRMR `varies_by_level` key whose
# `statement` text the loader should prefer when the indicator's statement
# is nested per-level (5 of 60 KSIs in catalog 0.9.43-beta).
_BASELINE_LEVEL = {"fedramp-20x-moderate": "moderate"}

# Stub README written into `.efterlev/manifests/` on init so the canonical
# location for Evidence Manifests is discoverable from on-disk state alone.
# Earlier versions created the directory lazily (only when a manifest was
# loaded), which left first-run users confused — the init banner and `--force`
# docs both reference manifests, but `ls .efterlev/` showed no `manifests/`.
_MANIFESTS_README = """# Evidence Manifests

This directory holds **customer-authored, human-signed procedural attestations**
for FedRAMP 20x KSIs whose evidence is not observable from the Terraform
scanner alone — themes like AFR (Authorization by FedRAMP), CED (Cybersecurity
Education), and INR (Incident Response) are entirely procedural.

Each manifest is a YAML file binding to exactly one KSI. At scan time, every
attestation in every manifest becomes an `Evidence` record with
`detector_id="manifest"` and flows through the Gap Agent alongside detector
evidence.

## Quick reference

```yaml
ksi: KSI-AFR-FSI
name: FedRAMP Security Inbox
evidence:
  - type: attestation
    statement: >
      security@example.com is monitored 24/7 by the SOC team with a 15-minute
      acknowledgment SLA. (Long-form, multi-sentence prose; describe the
      operational reality, not aspirations.)
    attested_by: vp-security@example.com
    attested_at: 2026-04-15
    reviewed_at: 2026-04-15
    next_review: 2026-10-15
    supporting_docs:
      - ./docs/policies/security-inbox-sop.pdf
      - https://wiki.example.com/soc/security-inbox
```

## See also

- Worked example with three manifests:
  https://github.com/lhassa8/govnotes-demo/tree/main/.efterlev/manifests
- Format reference: https://efterlev.com (search for "Evidence Manifest")
- Why these go in source control: they're part of your compliance posture and
  should go through code review like any other change. The attestor is named,
  the dates are recorded, and a 3PAO can read this directory directly.

This README is created automatically on `efterlev init`. Delete it once you
add real manifests, or keep it as a contributor pointer.
"""


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
    # Non-blocking freshness warnings produced by `check_catalog_freshness`.
    # Empty when the vendored catalog is current; non-empty when the catalog
    # is older than STALE_THRESHOLD_DAYS or when today is past the CR26
    # expected-release window. CLI emits each to stderr after the success
    # message; programmatic callers can ignore or surface them as needed.
    freshness_warnings: list[str] = field(default_factory=list)


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
        level=_BASELINE_LEVEL[baseline],
    )
    oscal_cat = load_oscal_800_53(catalogs_dir / "nist" / "NIST_SP-800-53_rev5_catalog.json")

    efterlev_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = efterlev_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create the canonical Evidence Manifests directory + a README pointing at
    # the format. Lazy creation was confusing for first-run users — the init
    # banner mentions manifests, the `--force` doc mentions manifests, but
    # `.efterlev/manifests/` didn't exist on disk until a manifest was
    # actually loaded. Now it's there as soon as the workspace exists, with
    # a README that names the schema and links to the docs example.
    manifests_dir = efterlev_dir / "manifests"
    if not manifests_dir.is_dir():
        manifests_dir.mkdir(parents=True, exist_ok=True)
        readme = manifests_dir / "README.md"
        if not readme.is_file():
            readme.write_text(_MANIFESTS_README, encoding="utf-8")
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
        freshness_warnings=check_catalog_freshness(frmr_doc),
    )
