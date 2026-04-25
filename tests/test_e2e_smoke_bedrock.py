"""Pytest wrapper for the Bedrock-backend variant of `scripts/e2e_smoke.py`.

Distinct from `tests/test_e2e_smoke.py` because the Bedrock path has its
own opt-in gate (`EFTERLEV_BEDROCK_SMOKE=1`) and credential requirements.
This file's only job is to make the Bedrock smoke runnable via
`pytest -k e2e_smoke_bedrock` so CI can invoke it without learning the
script's flag surface.

Skip semantics: skipped by default. Both `EFTERLEV_BEDROCK_SMOKE=1` and
AWS credentials must be present, OR the harness's own skip-gate
(`scripts/e2e_smoke.py`'s `_check_backend_env`) returns exit 2 and we
honor that signal.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "e2e_smoke.py"


@pytest.mark.e2e
def test_e2e_smoke_harness_bedrock() -> None:
    """Run the E2E smoke harness against real AWS Bedrock.

    Skipped unless `EFTERLEV_BEDROCK_SMOKE=1` and credentials are set.
    Region resolves from `--llm-region` (passed below as the AWS_REGION
    env value if set, otherwise us-east-1) or AWS_REGION.
    """
    if os.environ.get("EFTERLEV_BEDROCK_SMOKE") != "1":
        pytest.skip("EFTERLEV_BEDROCK_SMOKE != '1' — Bedrock smoke harness opt-in is required")
    if not (os.environ.get("AWS_PROFILE") or os.environ.get("AWS_ACCESS_KEY_ID")):
        pytest.skip("No AWS credentials available (AWS_PROFILE or AWS_ACCESS_KEY_ID)")

    region = os.environ.get("AWS_REGION", "us-east-1")
    cmd = [
        "uv",
        "run",
        "python",
        str(SCRIPT),
        "--llm-backend",
        "bedrock",
        "--llm-region",
        region,
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)

    # Exit 2 means the harness itself decided to skip (e.g., a credential
    # check inside the harness disagreed with what we saw above). Promote
    # to a pytest skip rather than a failure.
    if proc.returncode == 2:
        pytest.skip(f"Harness skipped: {proc.stderr.strip()}")

    assert proc.returncode == 0, (
        f"e2e_smoke.py --llm-backend bedrock exited {proc.returncode}.\n"
        f"--- stderr ---\n{proc.stderr}\n"
        "See .e2e-results/<timestamp>-bedrock-<region>/summary.md for the full report."
    )
