from __future__ import annotations

"""Run ``dag_replan_cap2`` on a single hand-picked HotpotQA bridge task
(the Big Fish theater question — where the earlier diagnostic showed
the base DAG planner fails STRUCTURALLY because the initial search for
"Big Fish musical composer lyricist" doesn't surface Andrew Lippa in
the top-5). Print every plan attempted, every tool output, and the
final synth so we can see replanning in action.

Run:

    python scripts/diagnose_replan_trace.py
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
from src.strategies.dag_planner_replan import run_dag_planner_replan  # noqa: E402
from src.tools.wikipedia import WIKIPEDIA_TOOLS  # noqa: E402

BIG_FISH_QUESTION = (
    "At what theater is the composer and lyricist for the musical Big Fish "
    "a residential artist?"
)
GOLD_ANSWER = "Ars Nova Theater"


def _truncate(s: Any, n: int = 140) -> str:
    text = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False, default=str)
    return text if len(text) <= n else text[: n - 1] + "…"


async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set.")
        return 1

    llm = GeminiProvider()
    trace: dict[str, Any] = {}

    print(f"Question:    {BIG_FISH_QUESTION}")
    print(f"Gold answer: {GOLD_ANSWER!r}")
    print("Running dag_replan_cap2 (max_replans=2, trigger='any_failure')…")
    print()

    # Default eval config is ``trigger="any_failure"``, but on the Big Fish
    # task the failure mode is SEMANTIC (wrong article returned with
    # non-empty content) rather than SYNTACTIC, so any_failure rarely fires.
    # Allow override via TRIGGER env var so this script can illustrate the
    # ``empty_synth`` path where replanning actually kicks in on this task.
    trigger = os.environ.get("TRIGGER", "any_failure")
    print(f"(trigger={trigger})")
    answer, metrics = await run_dag_planner_replan(
        BIG_FISH_QUESTION,
        WIKIPEDIA_TOOLS,
        llm,
        max_replans=2,
        trigger=trigger,
        trace=trace,
    )

    history = trace.get("history", [])
    print("=" * 78)
    print(f"Replans used: {trace.get('replans_used', 0)} (of max {trace.get('max_replans')})")
    print(f"Attempts in history: {len(history)}")
    print("=" * 78)

    for attempt_idx, (dag, outputs) in enumerate(history, start=1):
        is_replan = attempt_idx > 1
        label = "REPLAN" if is_replan else "INITIAL PLAN"
        print(f"\n--- Attempt {attempt_idx} · {label} ---")
        for task in dag.tasks:
            print(
                f"  Task {task.id}: {task.tool}({task.args})  "
                f"depends_on={task.depends_on}"
            )
        print("  Outputs (truncated):")
        for tid in sorted(outputs):
            print(f"    {tid}: {_truncate(outputs[tid])}")

    print()
    print("=" * 78)
    print(f"Final answer: {answer!r}")
    print("=" * 78)
    print(
        f"Metrics: n_llm_calls={metrics.n_llm_calls}, "
        f"n_tools_executed={metrics.n_tools_executed}, "
        f"n_replans={metrics.n_replans}, "
        f"wall_clock={metrics.total_wall_clock_seconds:.1f}s, "
        f"cost=${metrics.cost_usd:.4f}"
    )

    if GOLD_ANSWER.lower() in answer.lower():
        print(f"\n✓ Answer contains gold {GOLD_ANSWER!r}")
    else:
        print(f"\n✗ Answer does not contain gold {GOLD_ANSWER!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
