from __future__ import annotations

"""Verify Step 8 — DAG planner on the Eiffel Tower question.

Apples-to-apples with the Step 3 / Step 7 verifications. Prints:

  * The plan DAG (pretty JSON, as emitted by the planner)
  * Each topological execution level (which tasks fired in parallel)
  * Tool outputs (truncated to ~100 chars each)
  * Final answer + AggregateMetrics + per-call breakdown

Expected on this bridge question: 2 LLM calls (plan + synth),
2-3 tool calls (wikipedia_search + wikipedia_fetch), final answer
mentions "Paris".

Run:

    python scripts/verify_step8.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.llm.gemini import GeminiProvider  # noqa: E402
from src.strategies.dag_planner import run_dag_planner  # noqa: E402
from src.tools.wikipedia import WIKIPEDIA_TOOLS  # noqa: E402


def _truncate(s: Any, n: int = 100) -> str:
    text = s if isinstance(s, str) else repr(s)
    return text if len(text) <= n else text[: n - 1] + "…"


async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set.")
        return 1

    provider = GeminiProvider()
    question = "What is the capital of the country where the Eiffel Tower is located?"

    print(f"Question: {question}")
    print(f"Model:    {provider.model}")
    print("Running dag_planner…\n")

    trace: dict[str, Any] = {}
    final_answer, metrics = await run_dag_planner(
        question=question,
        tools=WIKIPEDIA_TOOLS,
        llm=provider,
        trace=trace,
    )

    # ---- Plan DAG ----------------------------------------------------------
    print("=== Plan DAG (raw submit_plan args) ===")
    print(json.dumps(trace.get("plan_raw"), indent=2, ensure_ascii=False))
    print()

    # ---- Execution levels --------------------------------------------------
    print("=== Topological execution levels ===")
    levels = trace.get("levels") or []
    for idx, level in enumerate(levels):
        print(f"Level {idx}: {len(level)} task(s)")
        for t in level:
            print(
                f"  Task {t.id}: {t.tool}({t.args})  depends_on={t.depends_on}"
            )
    print()

    # ---- Tool outputs (truncated) ------------------------------------------
    print("=== Tool outputs (truncated to ~100 chars) ===")
    outputs = trace.get("outputs") or {}
    for tid in sorted(outputs):
        print(f"Task {tid}: {_truncate(outputs[tid], 100)}")
    print()

    # ---- Final answer + metrics --------------------------------------------
    sum_latencies = sum(m.latency_seconds for m in metrics.per_call)

    print(f"Final answer: {final_answer!r}\n")

    print("=== AggregateMetrics ===")
    print(f"  n_llm_calls              : {metrics.n_llm_calls}")
    print(f"  n_tool_calls (LLM-emitted): {metrics.n_tool_calls}  (= the planner's submit_plan emission; LLM-verbosity metric)")
    print(f"  n_tools_executed         : {metrics.n_tools_executed}  (= actual Wikipedia executions; cross-strategy comparable)")
    print(f"  discarded_parallel_calls : {metrics.discarded_parallel_calls}")
    print(f"  input_tokens             : {metrics.input_tokens}")
    print(f"  output_tokens            : {metrics.output_tokens}")
    print(f"  cost_usd                 : ${metrics.cost_usd:.6f}")
    print(f"  total_wall_clock_seconds : {metrics.total_wall_clock_seconds:.3f}  (measured externally)")
    print(f"  sum of LLM latencies     : {sum_latencies:.3f}")
    print()

    print("=== Per-call breakdown ===")
    for i, call in enumerate(metrics.per_call, start=1):
        label = "plan" if i == 1 else "synth" if i == metrics.n_llm_calls else f"call_{i}"
        print(
            f"  Call {i} ({label}): latency={call.latency_seconds:.2f}s  "
            f"in={call.input_tokens}  out={call.output_tokens}  "
            f"tool_calls={call.n_tool_calls}  stop={call.stop_reason}"
        )
    print()

    # ---- Soft sanity checks -------------------------------------------------
    if not final_answer:
        print("WARN: no final answer produced.")
    elif "Paris" not in final_answer:
        print(f"WARN: final answer doesn't mention 'Paris' — got {final_answer!r}.")
    if metrics.n_llm_calls != 2:
        print(
            f"NOTE: expected exactly 2 LLM calls (plan + synth), got "
            f"{metrics.n_llm_calls}."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
