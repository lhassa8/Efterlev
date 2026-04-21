"""Primitive decorator + registry.

`@primitive` is the agent-legible surface: each decorated function becomes one
typed, MCP-exposable capability. At import time the decorator records metadata
(capability, version, determinism) on the module-level `_REGISTRY`. At call
time the wrapper validates input/output types, binds `current_primitive` for
the duration of the call so nested `store.write_record(...)` gets the
primitive tag for free, and emits a single `ProvenanceRecord` capturing the
input and output when a `ProvenanceStore` is active.

Design calls from DECISIONS 2026-04-20 affecting this layer: none directly;
#3 (prompt-injection defense) lands at the agent layer in Phase 3.
"""

from __future__ import annotations

import functools
import inspect
import logging
import typing
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeVar, cast

from pydantic import BaseModel

from efterlev.errors import PrimitiveError
from efterlev.provenance.context import current_primitive, get_active_store

log = logging.getLogger(__name__)

Capability = Literal["scan", "map", "evidence", "generate", "validate"]

P_in = TypeVar("P_in", bound=BaseModel)
P_out = TypeVar("P_out", bound=BaseModel)


@dataclass(frozen=True)
class PrimitiveSpec:
    """Metadata captured by `@primitive` for every registered callable."""

    name: str
    capability: Capability
    side_effects: bool
    version: str
    deterministic: bool
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    callable: Callable[..., Any]

    @property
    def spec_name(self) -> str:
        return f"{self.name}@{self.version}"


_REGISTRY: dict[str, PrimitiveSpec] = {}


def primitive(
    *,
    capability: Capability,
    side_effects: bool,
    version: str,
    deterministic: bool,
) -> Callable[[Callable[[P_in], P_out]], Callable[[P_in], P_out]]:
    """Decorate a function as a primitive: register, enforce I/O types, emit provenance.

    Contract enforced at decoration time:
      - exactly one positional argument
      - its annotation is a Pydantic BaseModel subclass
      - the return annotation is a Pydantic BaseModel subclass
      - the function name is unique within the registry

    Contract enforced at call time:
      - input is an instance of the declared input model
      - return is an instance of the declared output model
      - one ProvenanceRecord is written when a store is active (record_type
        "evidence" for deterministic primitives, "claim" otherwise)
    """

    def wrap(fn: Callable[[P_in], P_out]) -> Callable[[P_in], P_out]:
        name = fn.__name__
        sig = inspect.signature(fn)
        params = [p for p in sig.parameters.values() if p.kind != inspect.Parameter.VAR_KEYWORD]

        if len(params) != 1:
            raise PrimitiveError(
                f"primitive {name!r} must have exactly one argument (the input model); "
                f"got {len(params)}"
            )
        # `from __future__ import annotations` in the caller's module makes
        # signature annotations string-typed; resolve via get_type_hints which
        # evaluates them against the function's module globals.
        try:
            hints = typing.get_type_hints(fn)
        except NameError as e:
            raise PrimitiveError(f"primitive {name!r}: cannot resolve type hints ({e})") from e
        input_model_cls = hints.get(params[0].name)
        output_model_cls = hints.get("return")

        if not (isinstance(input_model_cls, type) and issubclass(input_model_cls, BaseModel)):
            raise PrimitiveError(
                f"primitive {name!r}: input annotation must be a Pydantic BaseModel subclass"
            )
        if not (isinstance(output_model_cls, type) and issubclass(output_model_cls, BaseModel)):
            raise PrimitiveError(
                f"primitive {name!r}: return annotation must be a Pydantic BaseModel subclass"
            )

        if name in _REGISTRY:
            raise PrimitiveError(f"primitive {name!r} already registered")

        spec = PrimitiveSpec(
            name=name,
            capability=capability,
            side_effects=side_effects,
            version=version,
            deterministic=deterministic,
            input_model=input_model_cls,
            output_model=output_model_cls,
            callable=cast("Callable[..., Any]", fn),
        )

        @functools.wraps(fn)
        def wrapper(payload: P_in) -> P_out:
            if not isinstance(payload, input_model_cls):
                raise PrimitiveError(
                    f"primitive {spec.spec_name}: expected input of type "
                    f"{input_model_cls.__name__}, got {type(payload).__name__}"
                )
            with current_primitive(spec.spec_name):
                result = fn(payload)
            if not isinstance(result, output_model_cls):
                raise PrimitiveError(
                    f"primitive {spec.spec_name}: must return {output_model_cls.__name__}, "
                    f"got {type(result).__name__}"
                )

            store = get_active_store()
            if store is None:
                log.warning(
                    "primitive %s called with no active provenance store; "
                    "skipping emission (ad-hoc use is ok; production must activate a store)",
                    spec.spec_name,
                )
                return result
            store.write_record(
                payload={
                    "input": payload.model_dump(mode="json"),
                    "output": result.model_dump(mode="json"),
                },
                record_type="evidence" if deterministic else "claim",
                primitive=spec.spec_name,
            )
            return result

        # Replace the raw fn with the wrapper on the spec so the registry points
        # to the call-site the rest of the system invokes.
        _REGISTRY[name] = PrimitiveSpec(
            name=spec.name,
            capability=spec.capability,
            side_effects=spec.side_effects,
            version=spec.version,
            deterministic=spec.deterministic,
            input_model=spec.input_model,
            output_model=spec.output_model,
            callable=cast("Callable[..., Any]", wrapper),
        )
        return cast("Callable[[P_in], P_out]", wrapper)

    return wrap


def get_registry() -> dict[str, PrimitiveSpec]:
    """Return a snapshot of the primitive registry (defensive copy)."""
    return dict(_REGISTRY)


def clear_registry() -> None:
    """Reset the registry. Test-only; required between tests that register."""
    _REGISTRY.clear()
