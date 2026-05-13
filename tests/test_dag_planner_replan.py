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
        self.captured_calls: list[dict[str, Any]] = []  # kwargs per call
        self.model = "mock"

    async def call(self, **kwargs: Any) -> tuple[Any, CallMetrics]:
        if self.call_count >= len(self.scripted):
            raise RuntimeError(
                f"scripted LLM ran out of responses after {self.call_count} calls"
            )
        item = self.scripted[self.call_count]
        self.captured_calls.append(kwargs)
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


@pytest.mark.asyncio
async def test_empty_synth_trigger_fires_on_refusal() -> None:
    """With ``trigger='empty_synth'``, a refusal-shaped synth answer fires
    a replan even when no in-DAG task failed. The next synth (after replan)
    becomes the final answer.
    """
    # Plan A succeeds, but synth produces a refusal.
    plan_a = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"ok"}', "depends_on": []}]
    )
    refusal = _response(
        [_text("I cannot answer this question with the provided information.")]
    )
    # Replan B succeeds, synth produces a real answer.
    plan_b = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"recovered"}', "depends_on": []}]
    )
    real_answer = _response([_text("Paris is the capital.")])

    llm = _ScriptedLLM([plan_a, refusal, plan_b, real_answer])

    answer, metrics = await run_dag_planner_replan(
        "q?",
        [_noop_tool()],
        llm,
        max_replans=2,
        trigger="empty_synth",
    )

    assert "paris" in answer.lower()
    assert metrics.n_replans == 1
    # 4 LLM calls: plan A + synth refusal + replan B + synth real.
    assert metrics.n_llm_calls == 4


def test_search_topk_propagates_to_planner_prompt() -> None:
    """Calling ``_build_planner_prompt`` with ``search_topk > 1`` should
    inject the fan-out hint with the right K and placeholder examples."""
    from src.strategies.dag_planner_replan import _build_planner_prompt
    from src.tools.wikipedia import WIKIPEDIA_TOOLS

    # search_topk=1 → no fan-out instruction.
    prompt_default = _build_planner_prompt(WIKIPEDIA_TOOLS, search_topk=1)
    assert "fan-out" not in prompt_default.lower()
    assert "top-1" not in prompt_default.lower()

    # search_topk=3 → fan-out instruction with placeholders 0..2.
    prompt_topk3 = _build_planner_prompt(WIKIPEDIA_TOOLS, search_topk=3)
    lower = prompt_topk3.lower()
    assert "fan-out" in lower
    assert "top-3" in lower or "top 3" in lower
    assert "$task_N.0" in prompt_topk3
    # K-1 = 2 should appear; K = 3 also OK to mention but key is K-1.
    assert "$task_N.2" in prompt_topk3

    # search_topk=5 should use placeholders 0..4.
    prompt_topk5 = _build_planner_prompt(WIKIPEDIA_TOOLS, search_topk=5)
    assert "$task_N.4" in prompt_topk5


@pytest.mark.asyncio
async def test_diversification_instruction_appears_in_replan_prompt() -> None:
    """With ``diversify_replan=True``, the replan call's user prompt should:
      (a) list prior search queries and their top results explicitly, and
      (b) contain the 'do not repeat' diversification instruction.
    """

    async def _noop_search(query: str) -> list:
        return ["Result A", "Result B", "Result C"]

    search_tool = Tool(
        name="noop_search",
        description="A controllable search-shaped tool.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        execute=_noop_search,
    )

    # Plan A uses one search query; synth refuses; replan B uses a different.
    plan_a = _plan(
        [
            {
                "id": 0,
                "tool": "noop_search",
                "args": '{"query":"original term"}',
                "depends_on": [],
            }
        ]
    )
    refusal = _response(
        [_text("I cannot answer this question with the provided information.")]
    )
    plan_b = _plan(
        [
            {
                "id": 0,
                "tool": "noop_search",
                "args": '{"query":"different term"}',
                "depends_on": [],
            }
        ]
    )
    real_answer = _response([_text("Paris")])

    llm = _ScriptedLLM([plan_a, refusal, plan_b, real_answer])

    answer, metrics = await run_dag_planner_replan(
        "q?",
        [search_tool],
        llm,
        max_replans=2,
        trigger="empty_synth",
        diversify_replan=True,
    )

    # 4 LLM calls total: plan_a, synth(refusal), plan_b (replan), synth(answer).
    assert metrics.n_llm_calls == 4
    assert metrics.n_replans == 1

    # The 3rd call (index 2) is the replan planner call.
    replan_user_msg = llm.captured_calls[2]["messages"][0]["content"]
    lower = replan_user_msg.lower()

    # (a) Prior search query and its top result are explicitly listed.
    assert "original term" in replan_user_msg
    assert "Result A" in replan_user_msg or "result a" in lower

    # (b) Diversification instruction is present.
    assert "do not repeat" in lower
    assert "different" in lower  # "different approach / entity / angle"


@pytest.mark.asyncio
async def test_any_or_empty_trigger_fires_for_both_failure_modes() -> None:
    """``trigger='any_or_empty'`` is the union of ``any_failure`` and
    ``empty_synth``. Verify both arms fire in one run:
      1. Initial plan's task fails → per-level trigger fires → replan #1.
      2. The replanned task succeeds but synth produces a refusal →
         post-synth trigger fires → replan #2.
      3. The final replan succeeds and synth gives a real answer.
    """
    # Plan A: failing task → per-level trigger.
    plan_a = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"FAIL"}', "depends_on": []}]
    )
    # Plan B (replan #1): succeeds, but synth refuses → post-synth trigger.
    plan_b = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"ok"}', "depends_on": []}]
    )
    refusal = _response([_text("I cannot answer with this information.")])
    # Plan C (replan #2): succeeds; synth real answer.
    plan_c = _plan(
        [{"id": 0, "tool": "noop", "args": '{"x":"recovered"}', "depends_on": []}]
    )
    real_answer = _response([_text("Paris is the capital.")])

    llm = _ScriptedLLM([plan_a, plan_b, refusal, plan_c, real_answer])

    answer, metrics = await run_dag_planner_replan(
        "q?",
        [_noop_tool()],
        llm,
        max_replans=3,
        trigger="any_or_empty",
    )

    assert "paris" in answer.lower()
    # Per-level fired once + post-synth fired once = 2 replans.
    assert metrics.n_replans == 2
    # 5 LLM calls: plan_a, plan_b (replan from failure), synth(refusal),
    #              plan_c (replan from refusal), synth(real).
    assert metrics.n_llm_calls == 5
    # 3 tool invocations: plan_a's task ran (and raised), plan_b's task,
    # plan_c's task.
    assert metrics.n_tools_executed == 3


def test_cot_synth_extracts_final_answer() -> None:
    """``_extract_final_answer`` should pull the text after ``FINAL ANSWER:``
    and fall back to the whole text when the marker is absent."""
    from src.strategies.dag_planner_replan import _extract_final_answer

    # Standard CoT format.
    assert (
        _extract_final_answer(
            "REASONING: The article says Paris is the capital.\n"
            "FINAL ANSWER: Paris"
        )
        == "Paris"
    )

    # Case-insensitive marker.
    assert (
        _extract_final_answer("Reasoning: …\nFinal Answer: Paris") == "Paris"
    )

    # Multi-line final answer is preserved (CoT model adds trailing notes).
    multi = (
        "REASONING: Lots of evidence.\n"
        "FINAL ANSWER: Andrew Lippa is a resident artist\n"
        "at the Ars Nova Theater."
    )
    extracted = _extract_final_answer(multi)
    assert "Ars Nova Theater" in extracted
    assert "REASONING" not in extracted  # reasoning section is stripped

    # No marker → fall back to the whole stripped text rather than empty.
    assert _extract_final_answer("Just a plain answer.") == "Just a plain answer."
    assert _extract_final_answer("") == ""
