from __future__ import annotations

"""Verify Step 3 — ReAct baseline on one multi-hop question.

Runs ReAct end-to-end on:

    "What is the capital of the country where the Eiffel Tower is located?"

…which requires two hops over Wikipedia (Eiffel Tower → France →
capital Paris). Prints the final answer plus the full ``AggregateMetrics``
and a per-call breakdown. Any discarded parallel calls are visible via
INFO-level logging from :mod:`src.strategies.react`.

Run:

    python scripts/verify_step3.py
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
from src.strategies.react import run_react  # noqa: E402
from src.tools.wikipedia import WIKIPEDIA_TOOLS  # noqa: E402


def _setup_logging() -> None:
    """Route INFO logs from the ReAct module to stdout in a readable shape.

    Keeps unrelated libraries (httpx etc.) at WARNING so the output stays clean.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s %(name)s] %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.WARNING)
    logging.getLogger("src.strategies.react").setLevel(logging.INFO)


async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
        return 1

    _setup_logging()

    provider = GeminiProvider()
    question = "What is the capital of the country where the Eiffel Tower is located?"

    print(f"Question: {question}")
    print(f"Model:    {provider.model}")
    print("Running ReAct…\n")

    final_answer, metrics = await run_react(
        question=question,
        tools=WIKIPEDIA_TOOLS,
        llm=provider,
    )

    print()
    print(f"Final answer: {final_answer!r}\n")

    print("=== AggregateMetrics ===")
    print(f"  n_llm_calls              : {metrics.n_llm_calls}")
    print(f"  n_tool_calls (emitted)   : {metrics.n_tool_calls}")
    print(f"  discarded_parallel_calls : {metrics.discarded_parallel_calls}")
    print(f"  n_tools_executed         : {metrics.n_tool_calls - metrics.discarded_parallel_calls}")
    print(f"  input_tokens             : {metrics.input_tokens}")
    print(f"  output_tokens            : {metrics.output_tokens}")
    print(f"  cost_usd                 : ${metrics.cost_usd:.6f}")
    print(f"  total_wall_clock_seconds : {metrics.total_wall_clock_seconds:.3f}")
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
        print("WARN: ReAct produced no final answer (likely hit max_steps).")
    elif "Paris" not in final_answer:
        print(f"WARN: final answer doesn't mention 'Paris' — got {final_answer!r}.")
    if metrics.n_llm_calls < 2:
        print("WARN: only one LLM call — the model may have answered without tools.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
