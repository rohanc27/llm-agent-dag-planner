from __future__ import annotations

"""Verify native_parallel on the Eiffel Tower question.

Re-uses the same question so the comparison vs ReAct is apples-to-apples:

    "What is the capital of the country where the Eiffel Tower is located?"

Prints the final answer plus the full AggregateMetrics. Also prints the
*sum* of per-call latencies separately from ``total_wall_clock_seconds``
so any parallel-execution savings inside a turn are visible (the gap
between the two numbers is the time we saved by overlapping tool calls).

Earlier ReAct runs used ~5 LLM calls / ~4 tool calls on this question. We
expect native_parallel to land 2-3 LLM calls if Gemini batches the
search/fetch pair into one turn, but ≥1 LLM call (the synthesis turn)
is always required.

Run:

    python scripts/verify_native_parallel.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.llm.gemini import GeminiProvider  # noqa: E402
from src.strategies.native_parallel import run_native_parallel  # noqa: E402
from src.tools.wikipedia import WIKIPEDIA_TOOLS  # noqa: E402


def _setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s %(name)s] %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.WARNING)
    logging.getLogger("src.strategies.native_parallel").setLevel(logging.INFO)


async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set.")
        return 1

    _setup_logging()

    provider = GeminiProvider()
    question = "What is the capital of the country where the Eiffel Tower is located?"

    print(f"Question: {question}")
    print(f"Model:    {provider.model}")
    print("Running native_parallel…\n")

    final_answer, metrics = await run_native_parallel(
        question=question,
        tools=WIKIPEDIA_TOOLS,
        llm=provider,
    )

    sum_latencies = sum(m.latency_seconds for m in metrics.per_call)

    print()
    print(f"Final answer: {final_answer!r}\n")

    print("=== AggregateMetrics ===")
    print(f"  n_llm_calls              : {metrics.n_llm_calls}")
    print(f"  n_tool_calls (emitted)   : {metrics.n_tool_calls}")
    print(f"  discarded_parallel_calls : {metrics.discarded_parallel_calls}")
    print(f"  input_tokens             : {metrics.input_tokens}")
    print(f"  output_tokens            : {metrics.output_tokens}")
    print(f"  cost_usd                 : ${metrics.cost_usd:.6f}")
    print(f"  total_wall_clock_seconds : {metrics.total_wall_clock_seconds:.3f}  (measured externally)")
    print(f"  sum of LLM latencies     : {sum_latencies:.3f}  (=∑ per-call latency; equals wall-clock only when fully serial)")
    print()

    print("=== Per-call breakdown ===")
    for i, call in enumerate(metrics.per_call, start=1):
        print(
            f"  Call {i}: "
            f"latency={call.latency_seconds:.2f}s  "
            f"in={call.input_tokens}  out={call.output_tokens}  "
            f"tool_calls={call.n_tool_calls}  stop={call.stop_reason}"
        )
    print()

    # Soft sanity checks.
    if not final_answer:
        print("WARN: no final answer produced.")
    elif "Paris" not in final_answer:
        print(f"WARN: final answer doesn't mention 'Paris' — got {final_answer!r}.")
    if metrics.n_llm_calls >= 5:
        print(
            f"NOTE: n_llm_calls={metrics.n_llm_calls} — not seeing batching savings "
            "vs ReAct on this task. The model may have chosen sequential decomposition; "
            "explicit DAG planning is the next experimental knob."
        )
    if metrics.discarded_parallel_calls != 0:
        print(
            f"BUG: native_parallel reported {metrics.discarded_parallel_calls} "
            "discarded calls — it should never discard."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
