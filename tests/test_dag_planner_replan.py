from __future__ import annotations

"""Unit tests for :func:`src.strategies.dag_planner_replan.run_dag_planner_replan`.

Like the base-planner tests, these use a scripted LLM mock — no network.
The contract we want to verify:

  1. Zero failures → zero replans; the run looks like a base DAG planner run.
  2. A failed task on the first DAG triggers a replan; the new DAG runs and
     the answer reflects its outputs.
  3. ``max_replans`` is a hard cap — beyond it, the strategy synthesizes
     against whatever it last has.
  4. ``metrics.n_replans`` matches the number of replans actually performed.

Run with:

    pytest tests/test_dag_planner_replan.py -v
"""

from types import SimpleNamespace
from typing import Any

import pytest

from src.llm.base import CallMetrics
from src.strategies.dag_planner_replan import run_dag_planner_replan
from src.tools.base import Tool


# ---------------------------------------------------------------------------
# Tiny Gemini-shaped fixtures (same shape as test_dag_planner_strategy.py).
# ---------------------------------------------------------------------------
def _response(parts: list[Any]) -> Any:
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


def _plan(tasks: list[dict[str, Any]]) -> Any:
    """Wrap a list of tasks in a single ``submit_plan`` function-call response."""
    return _response([_function_call("submit_plan", {"tasks": tasks})])


class _ScriptedLLM:
    def __init__(self, scripted: list[Any]) -> None:
        self.scripted = scripted
        self.call_count = 0
        self.model = "mock"

    async def call(self, **kwargs: Any) -> tuple[Any, CallMetrics]:
        if self.call_count >= len(self.scripted):
            raise RuntimeError(
                f"scripted LLM ran out of responses after {self.call_count} calls"
            )
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


# ---------------------------------------------------------------------------
# Tools: a controllable "noop" that fails when its ``x`` arg is "FAIL".
# ---------------------------------------------------------------------------
async def _noop_or_fail(**kwargs: Any) -> dict:
    if kwargs.get("x") == "FAIL":
        raise RuntimeError("simulated tool failure")
    return {"x": kwargs.get("x", "?"), "ok": True}


def _noop_tool() -> Tool:
    return Tool(
        name="noop",
        description="A controllable no-op; raises when x == 'FAIL'.",
        input_schema={
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        },
        execute=_noop_or_fail,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_failures_means_zero_replans() -> None:
    """Plan succeeds first time, synth produces an answer. Behaves like the
    base DAG planner: 2 LLM calls total, ``n_replans == 0``."""
    plan = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"ok"}', "depends_on": []}]
    )
    synth = _response([_text("All good.")])
    llm = _ScriptedLLM([plan, synth])

    answer, metrics = await run_dag_planner_replan(
        "q?", [_noop_tool()], llm, max_replans=2
    )

    assert "all good" in answer.lower()
    assert metrics.n_replans == 0
    assert metrics.n_llm_calls == 2  # 1 plan + 1 synth
    assert metrics.n_tools_executed == 1


@pytest.mark.asyncio
async def test_one_failure_triggers_replan() -> None:
    """First plan fails (one task throws) → strategy replans, new plan runs,
    synth answers based on the new outputs. ``n_replans == 1``."""
    plan_a = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"FAIL"}', "depends_on": []}]
    )
    plan_b = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"recovered"}', "depends_on": []}]
    )
    synth = _response([_text("Recovered after replan.")])
    llm = _ScriptedLLM([plan_a, plan_b, synth])

    answer, metrics = await run_dag_planner_replan(
        "q?", [_noop_tool()], llm, max_replans=2
    )

    assert "recovered" in answer.lower()
    assert metrics.n_replans == 1
    # 1 initial plan + 1 replan + 1 synth = 3
    assert metrics.n_llm_calls == 3
    # Both DAGs' single tool invocations counted.
    assert metrics.n_tools_executed == 2


@pytest.mark.asyncio
async def test_cap_reached_synth_runs_anyway() -> None:
    """Three consecutive failures with ``max_replans=2``: strategy gives up
    replanning after the cap and synthesizes against the last failure."""
    plan_a = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"FAIL"}', "depends_on": []}]
    )
    plan_b = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"FAIL"}', "depends_on": []}]
    )
    plan_c = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"FAIL"}', "depends_on": []}]
    )
    synth = _response([_text("Could not find anything useful.")])
    llm = _ScriptedLLM([plan_a, plan_b, plan_c, synth])

    answer, metrics = await run_dag_planner_replan(
        "q?", [_noop_tool()], llm, max_replans=2
    )

    # The cap is respected: exactly 2 replans, not 3.
    assert metrics.n_replans == 2
    # 1 initial + 2 replans + 1 synth = 4 LLM calls.
    assert metrics.n_llm_calls == 4
    # 3 attempts × 1 tool each.
    assert metrics.n_tools_executed == 3
    # Synth still produced an answer (even if a refusal-shaped one).
    assert answer == "Could not find anything useful."


@pytest.mark.asyncio
async def test_n_replans_metric_increments_correctly() -> None:
    """Drive the strategy through 0, 1, and 2 replans; assert
    ``metrics.n_replans`` lines up each time."""
    # 0 replans
    llm0 = _ScriptedLLM(
        [
            _plan(
                [{"id": 0, "tool": "noop", "args": '{"x":"ok"}', "depends_on": []}]
            ),
            _response([_text("done.")]),
        ]
    )
    _, m0 = await run_dag_planner_replan("q?", [_noop_tool()], llm0, max_replans=5)
    assert m0.n_replans == 0

    # 1 replan
    llm1 = _ScriptedLLM(
        [
            _plan([{"id": 0, "tool": "noop", "args": '{"x":"FAIL"}', "depends_on": []}]),
            _plan([{"id": 0, "tool": "noop", "args": '{"x":"ok"}', "depends_on": []}]),
            _response([_text("done.")]),
        ]
    )
    _, m1 = await run_dag_planner_replan("q?", [_noop_tool()], llm1, max_replans=5)
    assert m1.n_replans == 1

    # 2 replans
    llm2 = _ScriptedLLM(
        [
            _plan([{"id": 0, "tool": "noop", "args": '{"x":"FAIL"}', "depends_on": []}]),
            _plan([{"id": 0, "tool": "noop", "args": '{"x":"FAIL"}', "depends_on": []}]),
            _plan([{"id": 0, "tool": "noop", "args": '{"x":"ok"}', "depends_on": []}]),
            _response([_text("done.")]),
        ]
    )
    _, m2 = await run_dag_planner_replan("q?", [_noop_tool()], llm2, max_replans=5)
    assert m2.n_replans == 2
