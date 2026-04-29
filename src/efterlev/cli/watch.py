"""File-change watcher for `efterlev report run --watch`.

Re-runs the pipeline on file changes under `--target`, debounced to 2 seconds.

Design choices:

  - **Polling, not OS events.** A `watchdog`-style FS-event watcher
    would be more efficient but adds a runtime dependency and varies
    in subtle ways across platforms (file-rename on Linux fires
    differently from macOS). Poll-based mtime tracking is dependency-
    free, portable, and the CPU cost on a dev box is negligible
    (~50ms every 1s to walk a typical Terraform repo).

  - **Filter to relevant extensions.** Only `.tf`, `.tfvars`, `.yml`,
    `.yaml`, `.json` trigger a re-run. Everything else is noise (your
    editor's swap files, IDE caches, etc.).

  - **Skip `.efterlev/`.** Pipeline output writes there; watching it
    causes infinite re-run loops.

  - **2-second debounce after a change.** Users save in clusters
    (multi-file edits, find/replace, IDE format-on-save). Debouncing
    coalesces these into one re-run.

  - **Ctrl-C is the exit.** No special quit key; the user terminates
    the watcher with the standard interrupt.

The actual pipeline-re-run logic lives in cli/main.py; this module
just decides *when* to fire it.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path

# Default file extensions that trigger a re-run. Lowercase; the watcher
# does case-insensitive matching.
WATCHED_EXTENSIONS: tuple[str, ...] = (
    ".tf",
    ".tfvars",
    ".yml",
    ".yaml",
    ".json",
)

# Directories whose contents we never watch (would cause infinite re-runs
# or just add noise).
EXCLUDED_DIR_NAMES: tuple[str, ...] = (
    ".efterlev",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".terraform",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)


def _is_excluded_dir(path: Path) -> bool:
    """True if any path component matches an excluded directory name."""
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def _watched_files(root: Path) -> Iterator[Path]:
    """Yield every relevant file under root.

    Filters by extension and skips excluded directories. Uses
    `Path.rglob('*')` rather than `os.walk` for clarity; the
    excluded-dir check happens after the walk.
    """
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_excluded_dir(path.relative_to(root)):
            continue
        if path.suffix.lower() not in WATCHED_EXTENSIONS:
            continue
        yield path


def snapshot_mtimes(root: Path) -> dict[Path, float]:
    """Return a {path: mtime} map of every watched file under root.

    Pure function; safe to call repeatedly. The snapshot is what we
    diff against the next snapshot to detect changes.
    """
    out: dict[Path, float] = {}
    for path in _watched_files(root):
        try:
            out[path] = path.stat().st_mtime
        except OSError:
            # File was deleted between rglob and stat — ignore.
            continue
    return out


def diff_snapshots(
    prior: dict[Path, float], current: dict[Path, float]
) -> tuple[set[Path], set[Path], set[Path]]:
    """Return (added, removed, modified) sets between two snapshots."""
    added = set(current) - set(prior)
    removed = set(prior) - set(current)
    modified = {p for p in (set(current) & set(prior)) if current[p] != prior[p]}
    return added, removed, modified


def has_changes(prior: dict[Path, float], current: dict[Path, float]) -> bool:
    """Convenience — True iff the snapshots differ in any way."""
    added, removed, modified = diff_snapshots(prior, current)
    return bool(added or removed or modified)


def watch_loop(
    root: Path,
    *,
    on_change: Callable[[], None],
    poll_interval: float = 1.0,
    debounce_seconds: float = 2.0,
    max_iterations: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> None:
    """Block, polling root for changes, and call on_change when they
    settle.

    Algorithm:
      1. Take a baseline snapshot.
      2. Sleep poll_interval.
      3. Take a new snapshot. If it differs from the baseline, record
         the time and update the baseline.
      4. If it matches the baseline (no further changes) AND the most
         recent change was at least debounce_seconds ago AND there
         WAS a change since the last on_change call, fire on_change
         and reset.
      5. Repeat.

    `max_iterations` lets tests bound the loop. `sleep` and `now` are
    injectable so tests don't actually wait — they advance a fake
    clock.

    Caller handles KeyboardInterrupt for graceful exit.
    """
    baseline = snapshot_mtimes(root)
    last_change_at: float | None = None
    iterations = 0

    while True:
        if max_iterations is not None and iterations >= max_iterations:
            return
        iterations += 1
        sleep(poll_interval)
        current = snapshot_mtimes(root)
        if has_changes(baseline, current):
            baseline = current
            last_change_at = now()
            continue
        if last_change_at is not None and now() - last_change_at >= debounce_seconds:
            on_change()
            last_change_at = None
