"""Context machinery for the provenance store.

The `@primitive` and `@detector` decorators need access to the active
`ProvenanceStore` at call time without threading it through every primitive
signature. We use two `ContextVar`s:

- `_active_store`: set by the CLI (or a test fixture) before dispatching into
  any decorated callable. If unset, the decorator warns and degrades to no-op
  emission; the primitive still runs. This keeps ad-hoc debugging usable
  without relaxing the production guarantee.
- `_current_primitive`: set by the `@primitive` wrapper for the duration of a
  call so nested `store.write_record(...)` calls from the body can be tagged
  with the calling primitive automatically. Same mechanism for agents (v1+).

Both default to None. Use the `active_store(...)` context manager for scoped
activation; tests benefit from that shape most.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from efterlev.provenance.store import ProvenanceStore

_active_store: contextvars.ContextVar[ProvenanceStore | None] = contextvars.ContextVar(
    "efterlev_active_store",
    default=None,
)
_current_primitive: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "efterlev_current_primitive",
    default=None,
)


def get_active_store() -> ProvenanceStore | None:
    """Return the currently-activated ProvenanceStore, or None."""
    return _active_store.get()


def get_current_primitive() -> str | None:
    """Return the `name@version` of the currently-executing primitive, if any."""
    return _current_primitive.get()


@contextmanager
def active_store(store: ProvenanceStore) -> Iterator[ProvenanceStore]:
    """Scope-bind `store` as the active ProvenanceStore for decorated calls."""
    token = _active_store.set(store)
    try:
        yield store
    finally:
        _active_store.reset(token)


@contextmanager
def current_primitive(spec_name: str) -> Iterator[None]:
    """Scope-bind the executing primitive's `name@version` for nested write tagging."""
    token = _current_primitive.set(spec_name)
    try:
        yield
    finally:
        _current_primitive.reset(token)
