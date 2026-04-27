"""AWS Backup restore-testing detector.

Inspects every `aws_backup_restore_testing_plan` (the schedule + window)
and `aws_backup_restore_testing_selection` (which backups feed each
plan) and emits one Evidence per plan. Restore Testing is AWS Backup's
2023+ native primitive for proving that the backups in a vault can
actually be restored — backups that have never been test-restored are
not evidence that recovery works.

KSI-RPL-TRC ("Testing Recovery Capabilities") asks the customer to
"persistently test the capability to recover from incidents and
contingencies." A scheduled `aws_backup_restore_testing_plan` is the
canonical IaC-evidenceable signal: schedule + selection + recovery-
point-window define an automated, repeating recovery test.

Sibling to `aws.backup_retention_configured` (KSI-RPL-ABO — backup
existence). This detector evidences a different KSI: backup-existence
isn't recovery-validation, even though both are RPL-themed.

KSI mapping per FRMR 0.9.43-beta:
  - KSI-RPL-TRC lists `cp-4` (Contingency Plan Testing) and `cp-4.1`
    (Coordinate with related plans) — direct fits. Also lists `cp-6`,
    `cp-6.1`, `cp-9.1`, `cp-10`, `ir-3`, `ir-3.2` which are about
    storage/recovery objectives we don't directly evidence here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from efterlev.detectors.base import detector
from efterlev.models import Evidence, TerraformResource

_PLAN_TYPE = "aws_backup_restore_testing_plan"
_SELECTION_TYPE = "aws_backup_restore_testing_selection"


@detector(
    id="aws.backup_restore_testing",
    ksis=["KSI-RPL-TRC"],
    controls=["CP-4", "CP-4(1)"],
    source="terraform",
    version="0.1.0",
)
def detect(resources: list[TerraformResource]) -> list[Evidence]:
    """Emit one Evidence per restore-testing plan.

    Evidences (800-53):  CP-4 (Contingency Plan Testing) and
                         CP-4(1) (Coordinate with Related Plans).
                         Restore Testing IS the contingency-plan-test
                         primitive in AWS-managed backup.
    Evidences (KSI):     KSI-RPL-TRC (Testing Recovery Capabilities).
    Does NOT prove:      that test restores have actually succeeded
                         in the past (the runtime artifact lives in
                         AWS Backup, outside the IaC layer); that the
                         tested backup-vault contents reflect the
                         production data shape; that recovery
                         objectives (RTO/RPO) are met by the schedule.
    """
    selections_by_plan: dict[str, list[TerraformResource]] = {}
    plans: list[TerraformResource] = []

    for r in resources:
        if r.type == _PLAN_TYPE:
            plans.append(r)
        elif r.type == _SELECTION_TYPE:
            plan_ref = _plan_id_ref(r.body.get("restore_testing_plan_id"))
            if plan_ref:
                selections_by_plan.setdefault(plan_ref, []).append(r)

    out: list[Evidence] = []
    now = datetime.now(UTC)
    for plan in plans:
        # Match selections by Terraform reference shape:
        # `aws_backup_restore_testing_plan.<name>.id`. Selections referring
        # to a plan that isn't in this codebase still count for the body's
        # presence, but plan-side evidence is keyed on the plan's name.
        attached = selections_by_plan.get(plan.name, [])
        out.append(_emit_plan_evidence(plan, attached, now))

    return out


def _emit_plan_evidence(
    plan: TerraformResource,
    selections: list[TerraformResource],
    now: datetime,
) -> Evidence:
    """Build one Evidence record characterizing the restore-testing plan."""
    body = plan.body
    schedule = _extract_schedule(body)
    window_hours = body.get("start_window_hours")
    window_days = _recovery_point_window_days(body)
    selection_count = len(selections)

    has_schedule = bool(schedule)
    has_selection = selection_count > 0

    if has_schedule and has_selection:
        testing_state = "configured"
    elif has_schedule:
        testing_state = "no_selection"
    else:
        testing_state = "incomplete"

    content: dict[str, Any] = {
        "resource_type": plan.type,
        "resource_name": plan.name,
        "testing_state": testing_state,
        "schedule_expression": schedule,
        "start_window_hours": window_hours,
        "recovery_point_selection_window_days": window_days,
        "selection_count": selection_count,
    }

    if testing_state == "no_selection":
        content["gap"] = (
            f"Restore-testing plan `{plan.name}` is scheduled but no "
            "`aws_backup_restore_testing_selection` references it. The "
            "plan won't actually test anything until a selection is "
            "attached."
        )
    elif testing_state == "incomplete":
        content["gap"] = (
            f"Restore-testing plan `{plan.name}` has no `schedule_expression` "
            "in its `recovery_point_selection` block. The plan won't run "
            "without a schedule."
        )

    return Evidence.create(
        detector_id="aws.backup_restore_testing",
        ksis_evidenced=["KSI-RPL-TRC"],
        controls_evidenced=["CP-4", "CP-4(1)"],
        source_ref=plan.source_ref,
        content=content,
        timestamp=now,
    )


def _extract_schedule(body: dict[str, Any]) -> str | None:
    """Schedule lives at `schedule_expression` (top-level on the plan)."""
    return _as_str(body.get("schedule_expression"))


def _recovery_point_window_days(body: dict[str, Any]) -> int | None:
    """`recovery_point_selection.recovery_point_types[*]` and the
    `selection_window_days` knob describe what backup ages qualify for
    test-restore."""
    block = body.get("recovery_point_selection")
    if isinstance(block, list) and block and isinstance(block[0], dict):
        block = block[0]
    if not isinstance(block, dict):
        return None
    days = block.get("selection_window_days")
    if isinstance(days, int):
        return days
    if isinstance(days, str) and days.isdigit():
        return int(days)
    return None


def _plan_id_ref(value: Any) -> str | None:
    """A `restore_testing_plan_id = aws_backup_restore_testing_plan.foo.id`
    reference renders as the literal string `"${aws_backup_restore_testing_plan.foo.id}"`
    after python-hcl2 parsing — pull the plan name out of it."""
    s = _as_str(value)
    if s is None:
        return None
    marker = "aws_backup_restore_testing_plan."
    idx = s.find(marker)
    if idx < 0:
        return None
    rest = s[idx + len(marker) :]
    return rest.split(".", 1)[0].rstrip("}").rstrip()


def _as_str(value: Any) -> str | None:
    """python-hcl2 occasionally returns strings wrapped in single-element lists."""
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value if isinstance(value, str) else None
