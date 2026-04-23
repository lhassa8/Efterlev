"""Terraform Plan JSON parser.

Translates `terraform show -json <plan>` output into the same
`TerraformResource` shape that `efterlev.terraform.parser` emits from
raw `.tf` files, so detectors are input-agnostic (see DECISIONS
2026-04-22 "Design: Terraform Plan JSON support"). The translator is
the single place in the codebase that knows about plan-vs-HCL
differences; detectors stay pure.

Scope at Phase A:
  - Parses `planned_values.root_module` and all nested `child_modules`.
  - Emits one `TerraformResource` per `mode="managed"` resource.
  - `mode="data"` resources are skipped (same posture as HCL parsing —
    detectors reason over managed resources only).
  - `source_ref.file` is resolved from `configuration.root_module`
    module-call `source` field when available, else falls back to the
    plan filename itself.
  - `source_ref.line_start` / `line_end` are left as `None` (plan JSON
    has no line info).
  - The full resource address is NOT added to `body` here — that's an
    `Evidence.content.module_address` concern, resolved by the scan
    primitive during Phase A wiring.

What's intentionally NOT here:
  - Terraform CLI subprocess invocation. Users generate plan JSON in
    their CI (`terraform plan -out X && terraform show -json X`) and
    hand the file to `efterlev scan --plan FILE`.
  - Plan-JSON-diffing for drift. Phase 4 territory.
  - Data-source reasoning. A future design call.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from efterlev.errors import DetectorError
from efterlev.models import SourceRef, TerraformResource

# `terraform show -json` has emitted format_version ≥1.0 since Terraform
# 0.12. Versions we've actively tested are recorded for the
# warn-but-continue posture defined in the design entry.
SUPPORTED_FORMAT_VERSIONS = {"1.0", "1.1", "1.2"}


class PlannedResource(BaseModel):
    """One entry in `planned_values.{root,child}_module.resources`."""

    model_config = ConfigDict(extra="allow")

    address: str
    mode: str
    type: str
    name: str
    # index is the for_each key or count index; absent for single-instance
    # resources.
    index: str | int | None = None
    values: dict[str, Any] = Field(default_factory=dict)


class PlannedModule(BaseModel):
    """`root_module` or a `child_modules[*]` node in `planned_values`."""

    model_config = ConfigDict(extra="allow")

    # Root module typically has no `address`; child modules do (e.g.
    # `module.storage`).
    address: str | None = None
    resources: list[PlannedResource] = Field(default_factory=list)
    child_modules: list[PlannedModule] = Field(default_factory=list)


class PlannedValues(BaseModel):
    model_config = ConfigDict(extra="allow")
    root_module: PlannedModule


class ConfigModuleCall(BaseModel):
    """One entry in `configuration.root_module.module_calls`."""

    model_config = ConfigDict(extra="allow")

    source: str | None = None


class ConfigRootModule(BaseModel):
    model_config = ConfigDict(extra="allow")
    module_calls: dict[str, ConfigModuleCall] = Field(default_factory=dict)


class Configuration(BaseModel):
    model_config = ConfigDict(extra="allow")
    root_module: ConfigRootModule = Field(default_factory=ConfigRootModule)


class TerraformPlan(BaseModel):
    """Top-level `terraform show -json` document."""

    model_config = ConfigDict(extra="allow")

    format_version: str
    terraform_version: str | None = None
    planned_values: PlannedValues
    configuration: Configuration = Field(default_factory=Configuration)


def parse_plan_json(
    plan_path: Path,
    *,
    target_root: Path | None = None,
) -> list[TerraformResource]:
    """Load `plan_path` and emit one `TerraformResource` per managed resource.

    Args:
        plan_path: Filesystem path to a `terraform show -json <plan>`
            output file.
        target_root: Optional repo root the scan is logically anchored at.
            When supplied, `source_ref.file` is written relative to this
            root (matching the post-fixup-D repo-relative-path contract);
            otherwise the path from the plan's module-call `source` is
            recorded verbatim.

    Raises:
        DetectorError: if the file is missing, not valid JSON, or doesn't
            look like `terraform show -json` output.
    """
    if not plan_path.is_file():
        raise DetectorError(f"plan file not found at {plan_path}")

    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DetectorError(f"{plan_path} is not valid JSON: {exc}") from exc

    if "planned_values" not in payload:
        raise DetectorError(
            f"{plan_path} does not look like a `terraform show -json` output "
            "(missing 'planned_values' key). Hint: run "
            "`terraform show -json <plan-file>`, not `terraform plan -json`."
        )

    try:
        plan = TerraformPlan.model_validate(payload)
    except PydanticValidationError as exc:
        raise DetectorError(f"failed to validate plan JSON at {plan_path}: {exc}") from exc

    # format_version compat: warn-but-continue posture per the design
    # entry. We don't hard-error on newer schemas because the interface
    # is spec-stable and additive in practice.
    # (Silent for now; primitive layer will log the warning when wired.)

    # Module source lookup: the `configuration.root_module.module_calls`
    # dict maps module-call-name → source hint. We use it to resolve
    # `source_ref.file` for resources nested under that module. Only
    # local-source modules produce a resolvable path.
    module_sources: dict[str, str] = {
        name: call.source
        for name, call in plan.configuration.root_module.module_calls.items()
        if call.source
    }

    resources: list[TerraformResource] = []
    _collect_resources(
        module=plan.planned_values.root_module,
        module_path=[],
        module_sources=module_sources,
        plan_file=plan_path,
        target_root=target_root,
        out=resources,
    )
    return resources


def _collect_resources(
    *,
    module: PlannedModule,
    module_path: list[str],
    module_sources: dict[str, str],
    plan_file: Path,
    target_root: Path | None,
    out: list[TerraformResource],
) -> None:
    """Recursively walk `planned_values` collecting managed resources."""
    for pr in module.resources:
        if pr.mode != "managed":
            continue
        source_ref = _resolve_source_ref(
            module_path=module_path,
            module_sources=module_sources,
            plan_file=plan_file,
            target_root=target_root,
        )
        # Prefer the for_each/count index as the logical name when present —
        # it's the key the user thinks in (e.g. "user_uploads") rather than
        # the HCL address's `"this"` label inside a module.
        logical_name = str(pr.index) if pr.index is not None else pr.name
        out.append(
            TerraformResource(
                type=pr.type,
                name=logical_name,
                body=pr.values,
                source_ref=source_ref,
            )
        )

    for child in module.child_modules:
        # child.address looks like "module.storage" or
        # "module.storage.module.inner"; we want the sequence of module
        # call names for source lookup.
        child_names = _module_address_to_names(child.address)
        _collect_resources(
            module=child,
            module_path=child_names,
            module_sources=module_sources,
            plan_file=plan_file,
            target_root=target_root,
            out=out,
        )


def _module_address_to_names(address: str | None) -> list[str]:
    """`module.storage.module.inner` → `["storage", "inner"]`."""
    if not address:
        return []
    parts = address.split(".")
    # Pairs of ("module", NAME); also skip any `[key]` suffixes on module
    # addresses produced by for_each on module calls.
    names: list[str] = []
    i = 0
    while i < len(parts):
        if parts[i] == "module" and i + 1 < len(parts):
            name = parts[i + 1]
            # Strip for_each-on-module index: `storage["dev"]` → `storage`.
            if "[" in name:
                name = name.split("[", 1)[0]
            names.append(name)
            i += 2
        else:
            i += 1
    return names


def _resolve_source_ref(
    *,
    module_path: list[str],
    module_sources: dict[str, str],
    plan_file: Path,
    target_root: Path | None,
) -> SourceRef:
    """Best-effort source file for a resource in the given module path.

    For the root module (module_path=[]), we point at the plan file
    itself — no better anchor is available from plan JSON. For a
    module-nested resource, we use the first-level module's `source`
    attribute from `configuration.root_module.module_calls`; deeper
    nesting inherits the first-level source (plan JSON doesn't give
    us per-level source hints at the top of the document).
    """
    if not module_path:
        candidate = plan_file
    else:
        top_level = module_path[0]
        src = module_sources.get(top_level)
        if src is None:
            candidate = plan_file
        else:
            # Module source strings can be local paths ("./modules/storage"),
            # registry refs ("hashicorp/vpc/aws"), or git URLs. Only local
            # paths are resolvable to a file; non-local refs get the plan
            # file as the fallback anchor.
            src_path = Path(src)
            if src.startswith(("./", "../")) or src_path.is_absolute():
                candidate = src_path
            else:
                candidate = plan_file

    if target_root is not None:
        with contextlib.suppress(ValueError):
            # Path escapes target_root (remote module, plan file outside
            # the scan tree, etc.) — suppress and record candidate as-given.
            candidate = candidate.resolve().relative_to(target_root.resolve())

    return SourceRef(file=candidate, line_start=None, line_end=None)
