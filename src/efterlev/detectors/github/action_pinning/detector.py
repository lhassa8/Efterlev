"""GitHub Actions pinning detector.

Looks at every `.github/workflows/*.yml` workflow and reports, per
workflow, whether each `uses:` step references its action by an
immutable commit SHA (pinned) or by a mutable tag/branch name. Pinning
to a 40-character commit SHA is the OpenSSF / CISA / GSA-recommended
default for FedRAMP supply-chain hygiene — a tag like `@v4` resolves at
runtime to whatever commit currently holds that tag, which is the
attack vector behind tj-actions/changed-files (CVE-2025-30066) and
similar incidents.

Sibling to `github.ci_validation_gates`, `github.supply_chain_monitoring`,
and `github.immutable_deploy_patterns`. Same workflow-source plumbing
(`parse_workflow_tree` / `WorkflowFile`); evidences a different KSI.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-SCR-MIT (Mitigating Supply Chain Risk) lists `sr-5` (Acquisition
    Strategies) and `si-7.1` (Software/Firmware Integrity Checks). Pin-by-SHA
    IS the integrity-verification mechanism (a SHA mismatch fails the
    workflow); pin-by-SHA combined with renovate/dependabot updates IS
    the acquisition strategy. The detector evidences SR-5 + SI-7(1).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.github_workflows import WorkflowFile
from efterlev.models import Evidence

# A `uses:` ref pinned by SHA is exactly 40 hex chars (Git's full
# commit SHA). Tags and branch names will not match this shape.
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@detector(
    id="github.action_pinning",
    ksis=["KSI-SCR-MIT"],
    controls=["SR-5", "SI-7(1)"],
    source="github-workflows",
    version="0.1.0",
)
def detect(workflows: list[WorkflowFile]) -> list[Evidence]:
    """Emit one Evidence per workflow, characterizing its action-pin posture.

    Evidences (800-53):  SR-5 (Acquisition Strategies, Tools, and Methods),
                         SI-7(1) (Software, Firmware, and Information
                         Integrity — Integrity Checks). Pin-by-SHA is the
                         integrity-verification mechanism; combined with
                         a renovate/dependabot update flow it is the
                         acquisition strategy for OSS action dependencies.
    Evidences (KSI):     KSI-SCR-MIT (Mitigating Supply Chain Risk).
    Does NOT prove:      that the SHA-pinned actions are actually
                         non-malicious (a pinned SHA still points to
                         whatever code that commit contains); that the
                         pin will be kept current (stale pins miss
                         security fixes); that local actions
                         (`uses: ./.github/...`) are safe — those are
                         in-tree code, scoped elsewhere.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for wf in workflows:
        out.append(_emit_workflow_evidence(wf, now))

    return out


def _emit_workflow_evidence(wf: WorkflowFile, now: datetime) -> Evidence:
    """Build one Evidence record characterizing this workflow's pin posture."""
    pinned_refs, mutable_refs = _classify_action_refs(wf)

    total = len(pinned_refs) + len(mutable_refs)
    if total == 0:
        pin_state = "no_external_actions"
    elif not mutable_refs:
        pin_state = "all_pinned"
    elif not pinned_refs:
        pin_state = "none_pinned"
    else:
        pin_state = "mixed"

    content: dict[str, Any] = {
        "resource_type": "github_workflow",
        "resource_name": wf.name,
        "external_action_count": total,
        "pinned_action_count": len(pinned_refs),
        "mutable_action_refs": sorted(mutable_refs),
        "pin_state": pin_state,
    }

    if pin_state in {"none_pinned", "mixed"}:
        sample = ", ".join(f"`{r}`" for r in sorted(mutable_refs)[:3])
        content["gap"] = (
            f"Workflow `{wf.name}` references {len(mutable_refs)} action(s) "
            f"by mutable tag/branch (e.g. {sample}). Pin to a 40-char commit "
            "SHA so the workflow run is reproducible and resistant to a "
            "compromised-tag supply-chain attack."
        )

    return Evidence.create(
        detector_id="github.action_pinning",
        ksis_evidenced=["KSI-SCR-MIT"],
        controls_evidenced=["SR-5", "SI-7(1)"],
        source_ref=wf.source_ref,
        content=content,
        timestamp=now,
    )


def _classify_action_refs(wf: WorkflowFile) -> tuple[list[str], set[str]]:
    """Return (pinned_refs, mutable_refs) across all steps in this workflow.

    Walks every job's steps, examines each `uses:` value. Refs of the
    form `owner/repo@<sha>` where `<sha>` is 40 hex chars are pinned;
    `owner/repo@<tag>` or `owner/repo@<branch>` are mutable. Local
    refs (`./...`) and Docker refs (`docker://...`) are skipped — they
    have different supply-chain semantics scoped elsewhere.
    """
    pinned: list[str] = []
    mutable: set[str] = set()

    for _job_name, job in wf.jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses")
            if not isinstance(uses, str):
                continue
            if uses.startswith("./") or uses.startswith("docker://"):
                continue
            if "@" not in uses:
                # No version ref at all — treat as mutable (defaults to
                # the action's default branch, which is the strongest
                # form of pin instability).
                mutable.add(uses)
                continue
            _, ref = uses.rsplit("@", 1)
            if _SHA_RE.match(ref):
                pinned.append(uses)
            else:
                mutable.add(uses)

    return pinned, mutable
