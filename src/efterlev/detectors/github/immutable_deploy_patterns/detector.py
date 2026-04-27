"""Immutable-deploy-patterns detector.

Looks at every `.github/workflows/*.yml` workflow and reports whether
it uses declarative redeployment tooling (the immutable-pattern: every
change is a fresh deploy from version-controlled source) vs imperative
modification tooling (kubectl edit, aws cli mutate-* commands). KSI-
CMT-RMV ("Redeploying vs Modifying") asks the customer to "execute
changes through redeployment of version controlled immutable resources
rather than direct modification of running systems."

Declarative-deploy signals (run-command substrings):
  - `terraform apply` — re-applies the declared state
  - `helm upgrade` / `helm install` — re-renders chart on every run
  - `kubectl apply` — declarative reconciliation
  - `docker push` followed by deploy — versioned image artifacts

Anti-pattern signals (imperative mutation, NOT counted as evidence):
  - `kubectl edit` / `kubectl patch`
  - `aws ... modify-*` (EC2, RDS, etc.)
  - `terraform state mv` / `terraform state rm` (state-only, no apply)

For v1, the detector reports presence of declarative tooling. The
imperative-anti-pattern set is documented but not yet detected — the
absence of declarative tools is the gap signal, and future detectors
can add anti-pattern flagging.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-CMT-RMV lists `cm-2`, `cm-3`, `cm-5`, `cm-6`, `cm-7`, `cm-8.1`,
    `si-3` in its `controls` array. This detector evidences CM-2
    (Configuration Baseline — the declarative tool re-applies a
    versioned baseline on every deploy) and CM-7 (Least Functionality —
    declarative deploys deliver only what's declared, no side effects
    from manual edits).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.github_workflows import WorkflowFile
from efterlev.models import Evidence

# Declarative-deploy tooling. Run-command substring match.
_DECLARATIVE_DEPLOY_TOOLS: tuple[str, ...] = (
    "terraform apply",
    "helm upgrade",
    "helm install",
    "kubectl apply",
    "kustomize build",
    "argocd app sync",
    "fluxctl sync",
    "pulumi up",
    "cdk deploy",
)

# Action-shaped declarative deploys. Mapped to canonical names.
_ACTION_DEPLOY_MAP: dict[str, str] = {
    "hashicorp/setup-terraform": "terraform",  # the action is setup, but workflows
    # using hashicorp/setup-terraform almost always run terraform apply afterwards
    "azure/k8s-deploy": "kubectl apply",
    "azure/setup-helm": "helm",
    "WyriHaximus/github-action-helm3": "helm",
    "stefanprodan/kube-tools": "kubectl",
}


@detector(
    id="github.immutable_deploy_patterns",
    ksis=["KSI-CMT-RMV"],
    controls=["CM-2", "CM-7"],
    source="github-workflows",
    version="0.1.0",
)
def detect(workflows: list[WorkflowFile]) -> list[Evidence]:
    """Emit one Evidence per workflow, characterizing its deploy posture.

    Evidences (800-53):  CM-2 (Configuration Baseline — declarative tools
                         re-apply a versioned baseline on every run),
                         CM-7 (Least Functionality — declarative deploys
                         deliver only what's declared in source).
    Evidences (KSI):     KSI-CMT-RMV (Redeploying vs Modifying).
    Does NOT prove:      that the workflow doesn't ALSO contain manual
                         mutation steps (anti-pattern detection deferred);
                         that the deploy gate is wired into branch
                         protection; or that production deploys go
                         through this workflow at all.
    """
    out: list[Evidence] = []
    now = datetime.now(UTC)

    for wf in workflows:
        out.append(_emit_workflow_evidence(wf, now))

    return out


def _emit_workflow_evidence(wf: WorkflowFile, now: datetime) -> Evidence:
    """Build one Evidence record characterizing a workflow's deploy posture."""
    declarative_tools = _detect_declarative_tools(wf)

    redeploy_pattern_state = "present" if declarative_tools else "absent"

    content: dict[str, Any] = {
        "resource_type": "github_workflow",
        "resource_name": wf.name,
        "declarative_tools_detected": list(declarative_tools),
        "redeploy_pattern_state": redeploy_pattern_state,
    }

    if redeploy_pattern_state == "absent":
        content["gap"] = (
            f"Workflow `{wf.name}` runs but contains no declarative-deploy "
            "step (looked for: terraform apply, helm upgrade, kubectl apply, "
            "kustomize build, argocd sync, pulumi up, cdk deploy). KSI-CMT-RMV "
            "asks for redeployment of version-controlled immutable resources; "
            "imperative mutations (kubectl edit, aws ... modify-*) do not "
            "evidence the immutable-redeploy commitment."
        )

    return Evidence.create(
        detector_id="github.immutable_deploy_patterns",
        ksis_evidenced=["KSI-CMT-RMV"],
        controls_evidenced=["CM-2", "CM-7"],
        source_ref=wf.source_ref,
        content=content,
        timestamp=now,
    )


def _detect_declarative_tools(wf: WorkflowFile) -> list[str]:
    """Walk every job's steps. Match `run:` commands against canonical
    declarative-deploy tool substrings. Match `uses:` references against
    a known-action allow-list. Returns sorted, deduplicated tool names."""
    found: set[str] = set()

    for _job_name, job in wf.jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            run_cmd = step.get("run")
            if isinstance(run_cmd, str):
                for tool in _DECLARATIVE_DEPLOY_TOOLS:
                    if tool in run_cmd:
                        found.add(tool)
            uses = step.get("uses")
            if isinstance(uses, str):
                action_name = uses.split("@", 1)[0]
                for action_prefix, canonical in _ACTION_DEPLOY_MAP.items():
                    if action_name.startswith(action_prefix):
                        found.add(canonical)
    return sorted(found)
