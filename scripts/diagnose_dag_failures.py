from __future__ import annotations

"""Diagnose DAG planner failures by re-running 3 representative tasks with
debug instrumentation and inspecting the planner / execute / synth state.

Goal: classify each failure as

  * STRUCTURAL       — the plan did not retrieve content containing the
                       gold answer (or even reach execution)
  * SYNTH_WEAKNESS   — synth's input contained the gold (or near-context)
                       but the synth call did not extract it
  * INTERFACE_BUG    — gold was in raw tool outputs but lost in synth-
                       prompt formatting (truncation, bad rendering)

Task selection:
  1. ``5abdff77...`` (Big Fish theater) — DAG ✗, ReAct ✓; classic two-hop
  2. one programmatically-picked DAG-fail / ReAct-success pair
  3. ``5a7220f0...`` (Volvo S70) — DAG hit a malformed-placeholder sentinel
     in the prior run; both ReAct and native_parallel failed too (different
     reasons)

The diagnostic re-runs ``dag_planner`` with ``debug={}`` and prints the
full state. Re-running is non-deterministic — Gemini may produce a
different plan than the row in results.json. The diagnostic still shows
the *shape* of failure on these task patterns.

Run:

    python scripts/diagnose_dag_failures.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.llm.gemini import GeminiProvider  # noqa: E402
from src.strategies.dag_planner import run_dag_planner  # noqa: E402
from src.tools.wikipedia import WIKIPEDIA_TOOLS  # noqa: E402

RESULTS_PATH = REPO_ROOT / "results" / "results.json"
TASKS_PATH = REPO_ROOT / "benchmarks" / "hotpotqa" / "tasks.json"

# The two task IDs the user pinned explicitly. Third is chosen programmatically.
FIXED_TASK_IDS: tuple[str, str] = (
    "5abdff775542993f32c2a082",  # Big Fish theater
    "5a7220f055429971e9dc92ac",  # Volvo S70
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _bookend_truncate(text: str, head: int = 500, tail: int = 200) -> str:
    """Show the first ``head`` and last ``tail`` chars of a long string."""
    if text is None:
        return "<none>"
    if len(text) <= head + tail + 32:
        return text
    return f"{text[:head]}\n  …(elided {len(text) - head - tail} chars)…\n{text[-tail:]}"


def _truncate(value: Any, n: int = 500) -> str:
    if value is None:
        return "<none>"
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= n:
        return text
    return text[:n] + "…(truncated)"


def _latest_by_strategy(records: list[dict]) -> dict[str, dict[str, dict]]:
    """Index records by task_id → strategy → latest row."""
    out: dict[str, dict[str, dict]] = {}
    for r in records:
        tid = r.get("task_id")
        strategy = r.get("strategy")
        if not tid or not strategy:
            continue
        out.setdefault(tid, {})[strategy] = r  # later rows overwrite (latest wins)
    return out


def _pick_third_task(
    by_task: dict[str, dict[str, dict]],
    exclude: set[str],
) -> Optional[str]:
    """Choose a task that:
      - has a dag_planner row that judged wrong
      - has a react row that judged correct
      - dag_planner's predicted_answer is NOT a sentinel (clearer signal)
    Picks the alphabetically smallest qualifying task_id for determinism.
    """
    candidates: list[str] = []
    for tid, by_strat in by_task.items():
        if tid in exclude:
            continue
        dag = by_strat.get("dag_planner")
        react = by_strat.get("react")
        if not dag or not react:
            continue
        if dag.get("judge_correct") is not False:
            continue
        if react.get("judge_correct") is not True:
            continue
        pred = dag.get("predicted_answer", "") or ""
        if pred.startswith("DAG_PLANNER_EMPTY_RESULT"):
            continue
        candidates.append(tid)
    candidates.sort()
    return candidates[0] if candidates else None


def _classify(
    plan_validation: Optional[str],
    gold: str,
    synth_user_prompt: str,
    raw_outputs_concat: str,
) -> tuple[str, str]:
    """Return (label, reason)."""
    gold_l = gold.lower()
    if plan_validation != "ok":
        return (
            "STRUCTURAL",
            f"planner emitted invalid plan ({plan_validation}); no execution reached",
        )
    if gold_l in synth_user_prompt.lower():
        return (
            "SYNTH_WEAKNESS",
            "gold appears in synth's input — synth had it but didn't extract it",
        )
    if gold_l in raw_outputs_concat.lower():
        return (
            "INTERFACE_BUG",
            "gold appeared in raw tool outputs but was lost in synth-prompt formatting",
        )
    return (
        "STRUCTURAL",
        "plan did not retrieve content containing the gold answer",
    )


# ---------------------------------------------------------------------------
# Per-task diagnostic
# ---------------------------------------------------------------------------
async def diagnose_task(
    task: dict,
    llm: GeminiProvider,
    by_task: dict[str, dict[str, dict]],
) -> None:
    task_id = task["id"]
    question = task["question"]
    gold = task["answer"]

    print("=" * 78)
    print(f"=== TASK {task_id} ===")
    print("=" * 78)
    print(f"Question: {question}")
    print(f"Gold answer: {gold!r}")
    print()

    prior = by_task.get(task_id, {})
    react_row = prior.get("react")
    dag_row = prior.get("dag_planner")

    def _verdict(row: Optional[dict]) -> str:
        if not row:
            return "<not in results.json>"
        if row.get("error"):
            return f"ERRORED: {row['error']}"
        mark = "✓ correct" if row.get("judge_correct") else "✗ wrong"
        return f"{row.get('predicted_answer', '')!r}  ({mark})"

    print(f"ReAct's previous answer:        {_verdict(react_row)}")
    print(f"DAG planner's previous answer:  {_verdict(dag_row)}")
    print()
    print("Re-running dag_planner with debug instrumentation…")
    print()

    debug: dict[str, Any] = {}
    answer, metrics = await run_dag_planner(
        question, WIKIPEDIA_TOOLS, llm, debug=debug
    )

    # ---------- Phase 1 ----------
    print("--- Phase 1: Plan ---")
    sys_prompt = debug.get("planner_system_prompt") or ""
    print(f"Planner system prompt: <{len(sys_prompt)} chars; first 500 + last 200>")
    print(_bookend_truncate(sys_prompt, head=500, tail=200))
    print()
    print(f"Planner user prompt: {debug.get('planner_user_prompt')!r}")
    print()
    print("Plan returned (raw submit_plan args):")
    if debug.get("plan_raw") is not None:
        print(json.dumps(debug["plan_raw"], indent=2, ensure_ascii=False, default=str))
    else:
        print("<no plan returned>")
    print()
    print(f"Plan validation: {debug.get('plan_validation')}")
    print()

    # ---------- Phase 2 ----------
    print("--- Phase 2: Execute ---")
    level_executions = debug.get("level_executions") or []
    if not level_executions:
        print("(no execution — plan didn't validate or had no tasks)")
    for entry in level_executions:
        print(f"  Level {entry['level']}:")
        for tdebug in entry["tasks"]:
            tid = tdebug.get("task_id")
            tool = tdebug.get("tool")
            args_raw = tdebug.get("args_raw")
            args_sub = tdebug.get("args_substituted")
            output = tdebug.get("output")
            print(f"    Task {tid} ({tool}({args_raw})):")
            print(f"      Substituted args: {args_sub}")
            print(f"      Output (first 500 chars): {_truncate(output, 500)}")
    print()

    # ---------- Phase 3 ----------
    print("--- Phase 3: Synth ---")
    synth_sys = debug.get("synth_system_prompt") or ""
    if synth_sys:
        print(f"Synth system prompt: <{len(synth_sys)} chars; first 500 + last 200>")
        print(_bookend_truncate(synth_sys, head=500, tail=200))
    else:
        print("Synth system prompt: <not reached>")
    print()
    synth_user = debug.get("synth_user_prompt") or ""
    if synth_user:
        print("Synth user prompt (FULL — this is the critical one):")
        print("─" * 78)
        print(synth_user)
        print("─" * 78)
    else:
        print("Synth user prompt: <not reached>")
    print()
    synth_resp = debug.get("synth_response")
    if synth_resp is not None:
        print(f"Synth response: {synth_resp!r}")
    else:
        print("Synth response: <not reached>")
    print()

    # ---------- Analysis ----------
    print("--- Analysis ---")
    raw_outputs_concat = ""
    for entry in level_executions:
        for tdebug in entry["tasks"]:
            out = tdebug.get("output")
            if out is not None:
                raw_outputs_concat += " " + (
                    out if isinstance(out, str) else json.dumps(out, default=str)
                )

    gold_in_synth = gold.lower() in synth_user.lower()
    gold_in_raw = gold.lower() in raw_outputs_concat.lower()

    print(f"Did synth's input contain the gold answer text {gold!r}?")
    if gold_in_synth:
        idx = synth_user.lower().find(gold.lower())
        start, end = max(0, idx - 60), min(len(synth_user), idx + len(gold) + 60)
        print(f"  YES — snippet: …{synth_user[start:end]}…")
    else:
        print("  NO")
        if gold_in_raw:
            idx = raw_outputs_concat.lower().find(gold.lower())
            start = max(0, idx - 60)
            end = min(len(raw_outputs_concat), idx + len(gold) + 60)
            print(f"  (BUT it appeared in RAW tool outputs — possible formatting loss)")
            print(f"  raw snippet: …{raw_outputs_concat[start:end]}…")
        else:
            print("  (and gold did not appear in raw tool outputs either)")
    print()
    print(
        "Did synth's input contain enough context to derive the gold? "
        "<human judgment placeholder>"
    )
    print()

    label, reason = _classify(
        debug.get("plan_validation"), gold, synth_user, raw_outputs_concat
    )
    print(f"Classification: {label}")
    print(f"  reason: {reason}")
    print(
        f"  diagnostic re-run metrics: n_llm_calls={metrics.n_llm_calls}, "
        f"n_tools_executed={metrics.n_tools_executed}, "
        f"wall_clock={metrics.total_wall_clock_seconds:.1f}s, "
        f"cost=${metrics.cost_usd:.4f}"
    )
    print()
    print(f"Diagnostic re-run final answer: {answer!r}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set.", file=sys.stderr)
        return 1

    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
    by_task = _latest_by_strategy(records)

    with open(TASKS_PATH, "r", encoding="utf-8") as f:
        all_tasks = json.load(f)
    tasks_by_id = {t["id"]: t for t in all_tasks}

    third = _pick_third_task(by_task, exclude=set(FIXED_TASK_IDS))
    if third is None:
        print(
            "ERROR: couldn't auto-pick a 3rd task — no DAG-fail+ReAct-pass pair found.",
            file=sys.stderr,
        )
        return 2

    selected = [FIXED_TASK_IDS[0], third, FIXED_TASK_IDS[1]]
    print(f"Diagnosing 3 tasks:")
    print(f"  1: {selected[0]}  (Big Fish theater — explicit)")
    print(f"  2: {selected[1]}  (auto-picked DAG-fail+ReAct-pass)")
    print(f"  3: {selected[2]}  (Volvo S70 — explicit)")
    print()

    llm = GeminiProvider()
    for tid in selected:
        task = tasks_by_id.get(tid)
        if task is None:
            print(f"WARN: task {tid} not in tasks.json, skipping")
            continue
        await diagnose_task(task, llm, by_task)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
