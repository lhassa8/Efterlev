"""Tests for the progress-callback infrastructure (Priority 3.5).

Three concerns to verify:

  1. The protocol's no-op default works (omitting the callback or
     passing NoopProgressCallback yields zero output).
  2. TerminalProgressCallback formats `[idx/total] unit_id ✓` (or `✗`)
     to stderr in a stable shape.
  3. The Documentation Agent calls back once per processed unit
     (eligible + skipped paths both fire).
"""

from __future__ import annotations

import pytest

from efterlev.cli.progress import (
    NoopProgressCallback,
    TerminalProgressCallback,
)

# --- TerminalProgressCallback formatting ----------------------------------


def test_terminal_callback_emits_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Default usage: print one line per unit to stderr (stdout is for
    the agent's report, not progress)."""
    cb = TerminalProgressCallback()
    cb.on_unit_complete("KSI-SVC-SNT", 1, 60, success=True)
    out = capsys.readouterr()
    assert out.out == ""  # nothing on stdout
    assert "[1/60] KSI-SVC-SNT ✓" in out.err


def test_terminal_callback_marks_failure_with_x(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cb = TerminalProgressCallback()
    cb.on_unit_complete("KSI-IAM-MFA", 5, 10, success=False)
    out = capsys.readouterr()
    assert "[5/10] KSI-IAM-MFA ✗" in out.err


def test_terminal_callback_includes_stage_label_when_set(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cb = TerminalProgressCallback(stage="documentation")
    cb.on_unit_complete("KSI-SVC-SNT", 12, 60, success=True)
    out = capsys.readouterr()
    assert "[documentation]" in out.err
    assert "[12/60] KSI-SVC-SNT ✓" in out.err


def test_terminal_callback_no_stage_label_when_empty(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Empty `stage=""` means no `[stage]` prefix — keeps output clean
    when only one agent is running."""
    cb = TerminalProgressCallback(stage="")
    cb.on_unit_complete("KSI-X", 1, 1, success=True)
    out = capsys.readouterr()
    assert "[]" not in out.err
    # Still has the per-unit bracketed counter.
    assert "[1/1] KSI-X" in out.err


# --- NoopProgressCallback --------------------------------------------------


def test_noop_callback_emits_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    cb = NoopProgressCallback()
    cb.on_unit_complete("KSI-X", 1, 1, success=True)
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == ""


# --- Documentation Agent integration --------------------------------------


def test_documentation_agent_fires_callback_per_eligible_classification(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the agent processes 3 KSIs, the callback fires 3 times with
    monotonically-increasing idx and consistent total."""
    from efterlev.agents import DocumentationAgent
    from efterlev.agents.documentation import DocumentationAgentInput, NarrativeOutput
    from efterlev.agents.gap import KsiClassification
    from efterlev.llm import StubLLMClient
    from efterlev.models import Indicator

    # Three KSIs to draft. Stub LLM returns the same minimal narrative.
    indicators = {
        f"KSI-T-{i}": Indicator(
            id=f"KSI-T-{i}",
            theme="T",
            name=f"Test {i}",
            statement="ok",
            controls=[],
        )
        for i in range(3)
    }
    classifications = [
        KsiClassification(
            ksi_id=f"KSI-T-{i}",
            status="not_implemented",
            rationale="ok",
            evidence_ids=[],
        )
        for i in range(3)
    ]

    stub = StubLLMClient(
        response_text=NarrativeOutput(narrative="...", cited_evidence_ids=[]).model_dump_json()
    )
    agent = DocumentationAgent(client=stub)

    calls: list[tuple[str, int, int, bool]] = []

    class RecordingCallback:
        def on_unit_complete(self, unit_id: str, idx: int, total: int, *, success: bool) -> None:
            calls.append((unit_id, idx, total, success))

    agent.run(
        DocumentationAgentInput(
            indicators=indicators,
            evidence=[],
            classifications=classifications,
            baseline_id="fedramp-20x-moderate",
            frmr_version="0.9.43-beta",
        ),
        progress_callback=RecordingCallback(),
    )

    assert len(calls) == 3
    assert [c[0] for c in calls] == ["KSI-T-0", "KSI-T-1", "KSI-T-2"]
    assert [c[1] for c in calls] == [1, 2, 3]
    assert all(c[2] == 3 for c in calls)
    assert all(c[3] is True for c in calls)


def test_documentation_agent_with_no_callback_runs_silently(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Backward compat: omitting the callback yields no progress output
    (the NoopProgressCallback default kicks in)."""
    from efterlev.agents import DocumentationAgent
    from efterlev.agents.documentation import DocumentationAgentInput, NarrativeOutput
    from efterlev.agents.gap import KsiClassification
    from efterlev.llm import StubLLMClient
    from efterlev.models import Indicator

    indicator = Indicator(id="KSI-X", theme="X", name="X", statement="ok", controls=[])
    clf = KsiClassification(
        ksi_id="KSI-X",
        status="not_implemented",
        rationale="ok",
        evidence_ids=[],
    )

    stub = StubLLMClient(
        response_text=NarrativeOutput(narrative="...", cited_evidence_ids=[]).model_dump_json()
    )
    agent = DocumentationAgent(client=stub)

    agent.run(
        DocumentationAgentInput(
            indicators={"KSI-X": indicator},
            evidence=[],
            classifications=[clf],
            baseline_id="fedramp-20x-moderate",
            frmr_version="0.9.43-beta",
        ),
    )

    out = capsys.readouterr()
    # No progress output (the agent's normal LLM-call logging may use
    # stdout for non-test backends, but for the StubLLMClient there's
    # nothing visible).
    assert "[1/1] KSI-X" not in out.err
