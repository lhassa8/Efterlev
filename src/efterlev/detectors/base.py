"""Detector decorator + registry.

`@detector` registers a deterministic rule that reads typed source material
(Terraform resources at v0) and emits a list of `Evidence` records. The
decorator enforces metadata shape (capability-shaped id, KSI and 800-53
mappings, source type, version) and, at call time, persists every returned
Evidence into the active provenance store tagged with the detector's
`id@version`.

Per DECISIONS 2026-04-20 design call #1, `ksis` is allowed to be empty; that
represents the "evidences this 800-53 control but no current KSI maps here"
case (SC-28 today). Invented KSI IDs are a code smell; the vendored FRMR is
the source of truth and Phase 2's first detector's contract will validate
the KSI ids against it at import time.
"""

from __future__ import annotations

import functools
import inspect
import logging
import types
import typing
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeVar, cast, get_args, get_origin

from efterlev.errors import DetectorError
from efterlev.models import Evidence
from efterlev.provenance.context import get_active_store

log = logging.getLogger(__name__)

Source = Literal["terraform", "terraform-plan", "cloudformation", "cdk", "k8s", "pulumi"]

D_in = TypeVar("D_in")


@dataclass(frozen=True)
class DetectorSpec:
    """Metadata captured by `@detector` for every registered callable."""

    id: str
    ksis: tuple[str, ...]
    controls: tuple[str, ...]
    source: Source
    version: str
    input_type: type
    callable: Callable[..., list[Evidence]]

    @property
    def spec_name(self) -> str:
        return f"{self.id}@{self.version}"


_REGISTRY: dict[str, DetectorSpec] = {}


def detector(
    *,
    id: str,
    ksis: list[str],
    controls: list[str],
    source: Source,
    version: str,
) -> Callable[[Callable[[D_in], list[Evidence]]], Callable[[D_in], list[Evidence]]]:
    """Decorate a function as a detector: register, enforce output type, emit Evidence.

    Contract enforced at decoration time:
      - `id` is unique; `id` is a non-empty dotted string (e.g. "aws.encryption_s3_at_rest")
      - `controls` is a non-empty list; `ksis` may be empty (see design call #1)
      - the function has exactly one positional argument
      - the return annotation is `list[Evidence]` (or equivalent generic form)

    Contract enforced at call time:
      - the return value is a list of Evidence instances
      - every Evidence whose detector_id matches this detector is persisted to
        the active provenance store (if any); the original list is returned
        unchanged to the caller
    """

    def wrap(
        fn: Callable[[D_in], list[Evidence]],
    ) -> Callable[[D_in], list[Evidence]]:
        if not id or "." not in id:
            raise DetectorError(
                f"detector id must be dotted (e.g. 'aws.encryption_s3_at_rest'); got {id!r}"
            )
        if not controls:
            raise DetectorError(f"detector {id!r} must declare at least one 800-53 control")
        if id in _REGISTRY:
            raise DetectorError(f"detector {id!r} already registered")

        sig = inspect.signature(fn)
        params = [p for p in sig.parameters.values() if p.kind != inspect.Parameter.VAR_KEYWORD]
        if len(params) != 1:
            raise DetectorError(
                f"detector {id!r} must have exactly one argument; got {len(params)}"
            )
        # Resolve string annotations from `from __future__ import annotations`.
        try:
            hints = typing.get_type_hints(fn)
        except NameError as e:
            raise DetectorError(f"detector {id!r}: cannot resolve type hints ({e})") from e
        input_type = hints.get(params[0].name, object)

        # Best-effort check that the return annotation is list[Evidence]-ish.
        ret = hints.get("return", inspect.Signature.empty)
        origin = get_origin(ret)
        if (
            ret is not inspect.Signature.empty
            and ret is not types.NoneType
            and not (origin is list and Evidence in get_args(ret))
        ):
            raise DetectorError(
                f"detector {id!r} return annotation must be list[Evidence]; got {ret!r}"
            )

        spec_name = f"{id}@{version}"

        @functools.wraps(fn)
        def wrapper(payload: D_in) -> list[Evidence]:
            result = fn(payload)
            if not isinstance(result, list) or not all(isinstance(e, Evidence) for e in result):
                raise DetectorError(
                    f"detector {spec_name}: must return list[Evidence]; got {type(result).__name__}"
                )

            store = get_active_store()
            if store is None:
                log.warning(
                    "detector %s produced %d evidence record(s) with no active "
                    "provenance store; skipping persistence",
                    spec_name,
                    len(result),
                )
                return result
            for ev in result:
                store.write_record(
                    payload=ev.model_dump(mode="json"),
                    record_type="evidence",
                    primitive=spec_name,
                )
            return result

        _REGISTRY[id] = DetectorSpec(
            id=id,
            ksis=tuple(ksis),
            controls=tuple(controls),
            source=source,
            version=version,
            input_type=input_type,
            callable=cast("Callable[..., list[Evidence]]", wrapper),
        )
        return cast("Callable[[D_in], list[Evidence]]", wrapper)

    return wrap


def get_registry() -> dict[str, DetectorSpec]:
    """Return a snapshot of the detector registry (defensive copy)."""
    return dict(_REGISTRY)


def clear_registry() -> None:
    """Reset the registry. Test-only; required between tests that register."""
    _REGISTRY.clear()
