"""Pytest wrapper for `scripts/e2e_smoke.py`.

The smoke harness itself is a standalone script — runnable interactively
via `uv run python scripts/e2e_smoke.py`. This wrapper exposes it under
pytest so CI can invoke it with `pytest -k e2e`.

Skip semantics: without `ANTHROPIC_API_KEY` the harness exits 2 (not 0,
not 1) to distinguish "not configured for live test" from "live test
failed." This wrapper mirrors that: it skips when the key is absent so
developer-laptop `pytest -q` runs don't burn API credit by default.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "e2e_smoke.py"


@pytest.mark.e2e
def test_e2e_smoke_harness() -> None:
    """Run the E2E smoke harness against the real Anthropic API.

    Skipped when `ANTHROPIC_API_KEY` is unset. Otherwise invokes the
    script as a subprocess and asserts exit 0 — the script writes its
    own diagnostics (`.e2e-results/<ts>/summary.md`) that the developer
    consults on failure.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY unset — E2E smoke harness requires a real API key")

    proc = subprocess.run(
        ["uv", "run", "python", str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"e2e_smoke.py exited {proc.returncode}.\n"
        f"--- stderr ---\n{proc.stderr}\n"
        "See .e2e-results/<timestamp>/summary.md for the full report."
    )
