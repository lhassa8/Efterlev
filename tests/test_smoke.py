"""Pre-Day-1 smoke test so CI has something to collect against the stub scaffold."""

from __future__ import annotations

from pathlib import Path


def test_package_imports() -> None:
    """The top-level `efterlev` package imports cleanly on the configured Python."""
    import efterlev

    assert efterlev is not None


def test_in_source_version_matches_package_metadata() -> None:
    """`efterlev.__version__` must equal `importlib.metadata.version('efterlev')`.

    Lock-in for the v0.1.0 drift bug: the published 0.1.0 wheel printed
    `efterlev 0.0.1` from `efterlev --version` because pyproject.toml had a
    version literal but `__init__.py` was stale. Resolved in v0.1.1 by
    switching to `[tool.hatch.version] path = "src/efterlev/__init__.py"` so
    pyproject reads from the source. This test catches future drift if the
    build configuration regresses.
    """
    import importlib.metadata

    import efterlev

    assert efterlev.__version__ == importlib.metadata.version("efterlev"), (
        f"version drift: efterlev.__version__={efterlev.__version__!r} but "
        f"importlib.metadata.version('efterlev')="
        f"{importlib.metadata.version('efterlev')!r}. Check that "
        f"pyproject.toml's [tool.hatch.version].path points at "
        f"src/efterlev/__init__.py, and that the wheel was rebuilt after "
        f"the last `__version__` bump."
    )


def test_every_detector_folder_registers() -> None:
    """Every `detectors/aws/<capability>/` folder registers exactly one detector
    at runtime.

    Discovered 2026-04-25 dogfooding A4: each of the 16 net-new detectors had
    an empty `__init__.py`, so importing `efterlev.detectors` (the entry point
    the scan primitive uses) pulled in the package but never the inner
    `detector.py` — the `@detector` decorator never fired and runtime had only
    14 of 30 detectors registered. Per-detector unit tests passed because they
    import `detector.py` directly, bypassing the registry path entirely.

    The fix: each capability's `__init__.py` must `from . import detector`.
    This test enforces it: filesystem folder count == registered detector count.
    Adding a new detector folder without wiring its `__init__.py` will fail
    here, even if every other test passes.
    """
    # Trigger the package-level import path that scan_terraform uses.
    import efterlev.detectors  # noqa: F401  (registration side-effect)
    from efterlev.detectors.base import get_registry

    aws_dir = Path(__file__).resolve().parents[1] / "src" / "efterlev" / "detectors" / "aws"
    folders = sorted(
        p.name
        for p in aws_dir.iterdir()
        if p.is_dir() and (p / "detector.py").exists() and not p.name.startswith("_")
    )

    registered_aws = sorted(
        spec.id.removeprefix("aws.")
        for spec in get_registry().values()
        if spec.id.startswith("aws.")
    )

    missing = sorted(set(folders) - set(registered_aws))
    extra = sorted(set(registered_aws) - set(folders))
    assert not missing, (
        f"detector folders without runtime registration: {missing}. "
        f"Likely an empty `__init__.py` — add `from . import detector`."
    )
    assert not extra, f"registered detectors with no folder: {extra}."
