from __future__ import annotations

"""Unit tests for :func:`src.strategies.dag_planner.run_dag_planner`.

These mock the LLM entirely so they don't hit the network. The point is
the *empty-answer contract*: ``run_dag_planner`` must never silently
return ``("", metrics_with_zero_calls)`` — every empty-result path
either raises or surfaces a ``DAG_PLANNER_EMPTY_RESULT: <reason>``
sentinel.

Run with:

    pytest tests/test_dag_planner_strategy.py -v
"""

from types import SimpleNamespace
from typing import Any

import pytest

from src.llm.base import CallMetrics
from src.strategies.dag_planner import run_dag_planner
from src.tools.base import Tool


# -----------------------------------------------------------------------------
# Tiny Gemini-shaped fixtures
# -----------------------------------------------------------------------------
def _response(parts: list[Any]) -> Any:
    """SimpleNamespace shaped like a Gemini GenerateContentResponse."""
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(parts=parts),
                finish_reason=SimpleNamespace(name="STOP"),
            )
        ],
        usage_metadata=SimpleNamespace(
            prompt_token_count=10, candidates_token_count=5
        ),
    )


def _text(text: str) -> Any:
    return SimpleNamespace(text=text, function_call=None)


def _function_call(name: str, args: dict[str, Any]) -> Any:
    return SimpleNamespace(
        text=None, function_call=SimpleNamespace(name=name, args=args)
    )


class _ScriptedLLM:
    """LLMProvider stand-in returning a predetermined sequence of responses."""

    def __init__(self, scripted: list[Any]) -> None:
        self.scripted = scripted
        self.call_count = 0
        self.model = "mock"

    async def call(self, **kwargs: Any) -> tuple[Any, CallMetrics]:
        if self.call_count >= len(self.scripted):
            raise RuntimeError("scripted LLM ran out of responses")
        item = self.scripted[self.call_count]
        self.call_count += 1
        n_fc = sum(
            1
            for p in item.candidates[0].content.parts
            if getattr(p, "function_call", None)
        )
        return item, CallMetrics(
            latency_seconds=0.05,
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0,
            n_tool_calls=n_fc,
            stop_reason="STOP",
        )


async def _noop(**kwargs: Any) -> dict:
    return {"ok": True}


def _noop_tool() -> Tool:
    return Tool(
        name="noop",
        description="A no-op tool that takes an x string.",
        input_schema={
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        },
        execute=_noop,
    )


# -----------------------------------------------------------------------------
# The contract tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_never_returns_silent_empty_on_synth_empty_text() -> None:
    """If synth returns empty text, the strategy MUST surface a sentinel.

    This is the strongest form of the invariant: even with both LLM calls
    succeeding, an empty synth text cannot result in a ``("", metrics)``
    return.
    """
    plan_resp = _response(
        [
            _function_call(
                "submit_plan",
                {
                    "tasks": [
                        {
                            "id": 0,
                            "tool": "noop",
                            "args": '{"x":"y"}',
                            "depends_on": [],
                        }
                    ]
                },
            )
        ]
    )
    synth_resp = _response([_text("")])  # empty synth output

    llm = _ScriptedLLM([plan_resp, synth_resp])
    answer, metrics = await run_dag_planner("q?", [_noop_tool()], llm)

    # The core invariant.
    assert not (answer == "" and metrics.n_llm_calls == 0), (
        f"silent empty return: answer={answer!r}, "
        f"n_llm_calls={metrics.n_llm_calls}"
    )
    # And specifically: the strategy used the documented sentinel.
    assert "DAG_PLANNER_EMPTY_RESULT" in answer
    assert metrics.n_llm_calls == 2  # plan + synth both ran


@pytest.mark.asyncio
async def test_plan_validation_error_returns_sentinel() -> None:
    """A malformed placeholder in the plan must produce a sentinel
    answer rather than letting the exception drop the metrics."""
    plan_resp = _response(
        [
            _function_call(
                "submit_plan",
                {
                    "tasks": [
                        {
                            "id": 0,
                            "tool": "noop",
                            "args": '{"x":"hello"}',
                            "depends_on": [],
                        },
                        {
                            "id": 1,
                            "tool": "noop",
                            # Malformed placeholder — extra words after $task_0
                            "args": '{"x":"$task_0 some extra text"}',
                            "depends_on": [0],
                        },
                    ]
                },
            )
        ]
    )

    llm = _ScriptedLLM([plan_resp])
    answer, metrics = await run_dag_planner("q?", [_noop_tool()], llm)

    assert "DAG_PLANNER_EMPTY_RESULT" in answer
    assert "malformed placeholder" in answer.lower() or "plan validation" in answer.lower()
    # Plan call counted; synth never ran.
    assert metrics.n_llm_calls == 1


@pytest.mark.asyncio
async def test_planner_emits_no_function_call_returns_sentinel() -> None:
    """If the model returns text instead of a function_call (i.e. ignores
    the forced ``submit_plan``), we still must not silently return empty."""
    plan_resp = _response([_text("I refuse to plan.")])

    llm = _ScriptedLLM([plan_resp])
    answer, metrics = await run_dag_planner("q?", [_noop_tool()], llm)

    assert "DAG_PLANNER_EMPTY_RESULT" in answer
    assert metrics.n_llm_calls == 1
