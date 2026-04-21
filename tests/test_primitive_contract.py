"""Tests for the @primitive decorator and its registry.

Every test clears the primitive registry in its setup so registrations don't
leak across tests. The decorator is a module-level singleton, so that
discipline is load-bearing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from efterlev.errors import PrimitiveError
from efterlev.primitives.base import (
    PrimitiveSpec,
    get_registry,
    primitive,
)
from efterlev.provenance import ProvenanceStore, active_store


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give each test an empty primitive registry; restore real state on teardown."""
    import efterlev.primitives.base as mod

    monkeypatch.setattr(mod, "_REGISTRY", {})


class _FakeIn(BaseModel):
    x: int


class _FakeOut(BaseModel):
    y: int


# --- registration contract ----------------------------------------------------


def test_decorator_registers_primitive_metadata() -> None:
    @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
    def fake_prim(inp: _FakeIn) -> _FakeOut:
        return _FakeOut(y=inp.x + 1)

    reg = get_registry()
    assert "fake_prim" in reg
    spec = reg["fake_prim"]
    assert isinstance(spec, PrimitiveSpec)
    assert spec.capability == "scan"
    assert spec.side_effects is False
    assert spec.version == "0.1.0"
    assert spec.deterministic is True
    assert spec.spec_name == "fake_prim@0.1.0"


def test_decorator_rejects_duplicate_names() -> None:
    @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
    def fake_prim(inp: _FakeIn) -> _FakeOut:
        return _FakeOut(y=0)

    with pytest.raises(PrimitiveError, match="already registered"):

        @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
        def fake_prim(inp: _FakeIn) -> _FakeOut:
            return _FakeOut(y=0)


def test_decorator_rejects_non_pydantic_input() -> None:
    with pytest.raises(PrimitiveError, match="input annotation"):

        @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
        def bad_prim(inp: dict) -> _FakeOut:  # type: ignore[type-arg]
            return _FakeOut(y=0)


def test_decorator_rejects_non_pydantic_output() -> None:
    with pytest.raises(PrimitiveError, match="return annotation"):

        @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
        def bad_prim(inp: _FakeIn) -> dict:  # type: ignore[type-arg]
            return {}


def test_decorator_rejects_wrong_arg_count() -> None:
    with pytest.raises(PrimitiveError, match="exactly one argument"):

        @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
        def bad_prim(a: _FakeIn, b: _FakeIn) -> _FakeOut:
            return _FakeOut(y=0)


# --- call-time type enforcement ----------------------------------------------


def test_wrapper_runs_the_underlying_function() -> None:
    @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
    def fake_prim(inp: _FakeIn) -> _FakeOut:
        return _FakeOut(y=inp.x * 2)

    result = fake_prim(_FakeIn(x=21))
    assert result.y == 42


def test_wrapper_rejects_wrong_input_type() -> None:
    @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
    def fake_prim(inp: _FakeIn) -> _FakeOut:
        return _FakeOut(y=0)

    with pytest.raises(PrimitiveError, match="expected input of type"):
        fake_prim("not a model")  # type: ignore[arg-type]


def test_wrapper_rejects_wrong_return_type() -> None:
    @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
    def lying_prim(inp: _FakeIn) -> _FakeOut:
        return "not a model"  # type: ignore[return-value]

    with pytest.raises(PrimitiveError, match="must return _FakeOut"):
        lying_prim(_FakeIn(x=0))


# --- provenance emission ------------------------------------------------------


def test_active_store_gets_one_evidence_record_per_call(tmp_path: Path) -> None:
    @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
    def fake_prim(inp: _FakeIn) -> _FakeOut:
        return _FakeOut(y=inp.x + 1)

    with ProvenanceStore(tmp_path) as store, active_store(store):
        fake_prim(_FakeIn(x=1))
        fake_prim(_FakeIn(x=2))
        ids = store.iter_records()
        assert len(ids) == 2
        rec = store.get_record(ids[0])
        assert rec is not None
        assert rec.record_type == "evidence"
        assert rec.primitive == "fake_prim@0.1.0"


def test_non_deterministic_primitive_records_claim(tmp_path: Path) -> None:
    @primitive(capability="generate", side_effects=False, version="0.1.0", deterministic=False)
    def llm_prim(inp: _FakeIn) -> _FakeOut:
        return _FakeOut(y=inp.x + 100)

    with ProvenanceStore(tmp_path) as store, active_store(store):
        llm_prim(_FakeIn(x=0))
        ids = store.iter_records()
        rec = store.get_record(ids[0])
        assert rec is not None
        assert rec.record_type == "claim"


def test_no_active_store_warns_but_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    @primitive(capability="scan", side_effects=False, version="0.1.0", deterministic=True)
    def fake_prim(inp: _FakeIn) -> _FakeOut:
        return _FakeOut(y=inp.x)

    with caplog.at_level("WARNING", logger="efterlev.primitives.base"):
        result = fake_prim(_FakeIn(x=7))
    assert result.y == 7
    assert "no active provenance store" in caplog.text
