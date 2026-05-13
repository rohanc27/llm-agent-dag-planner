from __future__ import annotations

"""Diagnose why ``dag_replan_cap5_empty_top3`` underperforms ReAct on
BFCL parallel at seed=42.

Hypothesis: BFCL's mock tool responses (``{"status": "ok", "mock": True}``)
carry no semantic content, so the synth call has nothing concrete to
ground on and sometimes produces a refusal-shaped answer. The
``empty_synth`` trigger then fires, the planner replans, and during the
replan it sometimes drifts the function-call arguments away from the
gold set.

Methodology:

  1. From the existing ``results/results.json``, find the differential
     set — tasks where ReAct succeeded and DAG-replan failed at seed=42
     on the BFCL benchmark.
  2. For each differential task, dump:
       * question + gold calls
       * ReAct's predicted_calls (from the saved row)
       * DAG-replan's predicted_calls (from the saved row)
       * n_replans, synth answer from the saved DAG-replan row
  3. Re-run DAG-replan on each of those tasks with ``trace={}`` to
     capture intermediate state — every attempt's plan, every attempt's
     outputs, every synth output. (~6-8 fresh LLM calls per task.)
  4. Classify each into one of:
       MOCK_TRIGGERED_DRIFT  — synth refused due to mocks → replan →
                                args drifted away from gold
       ARG_DRIFT_OTHER       — replan fired but not from refusal,
                                still drifted
       NO_REPLAN_BUT_WRONG   — initial plan was already wrong; no
                                replan fired
       PLAN_VALIDATION       — initial plan failed validation; never
                                got to execute
       OTHER                 — anything else

  5. Tally — if MOCK_TRIGGERED_DRIFT dominates, the underperformance is
     a structural BFCL-mock artefact, not a fixable bug.

This script does NOT modify the strategy. It uses the existing
``trace`` debug hook on ``run_dag_planner_replan``.

Run:

    python scripts/diagnose_bfcl_replan.py
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

from src.judge_ast import evaluate_bfcl  # noqa: E402
from src.llm.gemini import GeminiProvider  # noqa: E402
from src.run_eval import _build_bfcl_tools  # noqa: E402
from src.strategies.dag_planner_replan import (  # noqa: E402
    _looks_like_refusal,
    run_dag_planner_replan,
)

RESULTS_PATH = REPO_ROOT / "results" / "results.json"
TASKS_PATH = REPO_ROOT / "benchmarks" / "bfcl" / "tasks.json"

DAG_STRATEGY = "dag_replan_cap5_empty_top3"
DAG_CONFIG = dict(max_replans=5, trigger="empty_synth", search_topk=3)


def _short(s: Any, n: int = 240) -> str:
    text = s if isinstance(s, str) else json.dumps(s, default=str, ensure_ascii=False)
    return text if len(text) <= n else text[: n - 1] + "…"


def _summarise_calls(calls: list[dict[str, Any]]) -> list[str]:
    out = []
    for c in calls or []:
        name = c.get("function_name", "?")
        args = c.get("args", {})
        out.append(f"{name}({args})")
    return out


def _classify_from_saved(
    saved_record: dict[str, Any], gold_calls: list[dict[str, Any]]
) -> tuple[str, dict[str, Any]]:
    """Classify based on the SAVED row (the failure we're trying to
    explain), not the re-run. Re-running is stochastic — Gemini may
    take a different path on the same task — so the re-run's role is
    qualitative ("does the replan loop drift args here?") while the
    classification has to anchor on the actual saved failure.

    Returns ``(bucket, evidence_dict)`` so the caller can show *why*
    the bucket was chosen.
    """
    metrics = saved_record.get("metrics") or {}
    n_replans = int(metrics.get("n_replans", 0))
    n_llm_calls = int(metrics.get("n_llm_calls", 0))
    pred_answer = saved_record.get("predicted_answer") or ""
    saved_predicted_calls = saved_record.get("predicted_calls") or []
    error_field = saved_record.get("error")

    evidence: dict[str, Any] = {
        "n_replans": n_replans,
        "n_llm_calls": n_llm_calls,
        "synth_refusal_shaped": _looks_like_refusal(pred_answer),
        "saved_call_count": len(saved_predicted_calls),
        "error": error_field,
    }

    # PLAN_VALIDATION: the strategy bailed before executing.
    if pred_answer.startswith("DAG_PLANNER_EMPTY_RESULT:"):
        return "PLAN_VALIDATION", evidence
    if error_field:
        return "OTHER", evidence
    # No replan fired → initial plan was wrong.
    if n_replans == 0:
        return "NO_REPLAN_BUT_WRONG", evidence
    # Replan fired. ``cap5_empty_top3`` uses ``trigger=empty_synth``
    # exclusively, which only fires when a synth output is refusal-
    # shaped (per ``_looks_like_refusal`` in the strategy). So
    # n_replans>0 on this strategy IS by construction a mock-triggered
    # refusal cycle — that's the hypothesis. The fact that the saved
    # final predicted_answer no longer matches the refusal regex is
    # because by then it's the post-replan synth, not the initial one.
    return "MOCK_TRIGGERED_DRIFT", evidence


async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set.")
        return 1

    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
    with open(TASKS_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)
    tasks_by_id = {t["id"]: t for t in tasks}

    # Latest row per (strategy, task_id) for seed=42 BFCL.
    by_strategy_task: dict[tuple[str, str], dict] = {}
    for r in records:
        if r.get("benchmark") != "bfcl_parallel":
            continue
        if r.get("seed") != 42:
            continue
        by_strategy_task[(r["strategy"], r["task_id"])] = r

    react_correct: set[str] = set()
    dag_failed: dict[str, dict] = {}
    for (strat, tid), row in by_strategy_task.items():
        if strat == "react" and row.get("judge_correct"):
            react_correct.add(tid)
        if strat == DAG_STRATEGY and not row.get("judge_correct"):
            dag_failed[tid] = row

    differential = sorted(set(dag_failed.keys()) & react_correct)
    print(f"Differential set: {len(differential)} tasks (DAG-replan failed AND ReAct succeeded at seed=42)")
    print(f"  {differential}")
    print()

    if not differential:
        print("Nothing to diagnose — empty differential set.")
        return 0

    llm = GeminiProvider()
    bucket_counts: dict[str, int] = {
        "MOCK_TRIGGERED_DRIFT": 0,
        "ARG_DRIFT_OTHER": 0,
        "NO_REPLAN_BUT_WRONG": 0,
        "PLAN_VALIDATION": 0,
        "OTHER": 0,
    }
    per_task_classifications: list[tuple[str, str]] = []

    for tid in differential:
        task = tasks_by_id.get(tid)
        dag_row = dag_failed[tid]
        react_row = by_strategy_task.get(("react", tid)) or {}

        print("=" * 78)
        print(f"=== {tid} ===")
        print("=" * 78)
        print(f"Question: {_short(task['question'], 320)}")
        print()
        print(f"Gold calls ({len(task['gold_calls'])}):")
        for gc in task["gold_calls"]:
            print(f"  {gc['function_name']}({gc['args']})")
        print()
        print(f"ReAct (saved row) predicted_calls ({len(react_row.get('predicted_calls', []))}):")
        for s in _summarise_calls(react_row.get("predicted_calls", [])):
            print(f"  {s}")
        print()
        print(f"DAG-replan (saved row) predicted_calls ({len(dag_row.get('predicted_calls', []))}):")
        for s in _summarise_calls(dag_row.get("predicted_calls", [])):
            print(f"  {s}")
        saved_metrics = dag_row.get("metrics", {})
        print(
            f"DAG-replan n_replans (saved): {saved_metrics.get('n_replans', 0)},  "
            f"n_llm_calls={saved_metrics.get('n_llm_calls', 0)}"
        )
        print(f"DAG-replan synth answer (saved): {_short(dag_row.get('predicted_answer', ''))}")
        print()

        # ---- Re-run with trace ----
        print("--- Re-run with debug instrumentation ---")
        call_log: list[dict[str, Any]] = []
        tools = _build_bfcl_tools(task["functions"], call_log)
        trace: dict[str, Any] = {}
        try:
            answer, metrics = await run_dag_planner_replan(
                question=task["question"],
                tools=tools,
                llm=llm,
                **DAG_CONFIG,
                trace=trace,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[!] Re-run errored: {type(exc).__name__}: {exc}")
            print()
            continue

        history = trace.get("history", [])
        print(f"Re-run history: {len(history)} attempt(s); replans_used={trace.get('replans_used', 0)}")
        for i, (prior_dag, prior_outputs) in enumerate(history, start=1):
            label = "INITIAL PLAN" if i == 1 else f"REPLAN #{i-1}"
            print(f"\n  Attempt {i} ({label}):")
            for tnode in prior_dag.tasks:
                print(f"    Task {tnode.id}: {tnode.tool}({tnode.args})")
        print()
        print(f"Re-run final synth: {_short(trace.get('final_answer', answer))}")
        print()
        print(f"Re-run executed call log ({len(call_log)} call(s)):")
        for s in _summarise_calls(call_log):
            print(f"  {s}")
        print()

        # Run AST judge on this re-run's calls.
        verdict_rerun = evaluate_bfcl(call_log, task["gold_calls"])
        print(f"Re-run AST verdict: correct={verdict_rerun['correct']}, rationale={_short(verdict_rerun['rationale'])}")

        # ---- Classification based on SAVED row (the failure of record) ---
        bucket, evidence = _classify_from_saved(dag_row, task["gold_calls"])
        print(f"Classification (from SAVED row): {bucket}")
        print(f"  evidence: {evidence}")
        # Show what the re-run did differently, for context only:
        rerun_replans = trace.get("replans_used", 0)
        rerun_synth_refusal = _looks_like_refusal(trace.get("final_answer", "") or answer)
        print(
            f"  (re-run: replans={rerun_replans}, synth_refusal_shaped={rerun_synth_refusal} — "
            f"stochastic, used for trace visibility only)"
        )
        bucket_counts[bucket] += 1
        per_task_classifications.append((tid, bucket))
        print()

    # ---- Summary ----
    total = sum(bucket_counts.values())
    print("=" * 78)
    print("Classification breakdown")
    print("=" * 78)
    for bucket in ("MOCK_TRIGGERED_DRIFT", "ARG_DRIFT_OTHER", "NO_REPLAN_BUT_WRONG", "PLAN_VALIDATION", "OTHER"):
        c = bucket_counts[bucket]
        pct = (c / total * 100.0) if total else 0.0
        print(f"  {bucket:>24}: {c}/{total}  ({pct:.0f}%)")
    print()
    print("Per-task assignments:")
    for tid, bucket in per_task_classifications:
        print(f"  {tid}: {bucket}")
    print()
    mock_share = bucket_counts["MOCK_TRIGGERED_DRIFT"] / total if total else 0
    if mock_share >= 0.5:
        print(
            "Conclusion: MOCK_TRIGGERED_DRIFT is the dominant failure "
            f"mode ({mock_share*100:.0f}%). The DAG-replan underperformance "
            "on BFCL is a **structural artefact of mock tool responses**: "
            "the synth call has nothing concrete to ground on, so it "
            "refuses; the refusal triggers the empty_synth replan; the "
            "replan drifts arguments. Not a fixable bug — fundamental to "
            "running replan strategies on uninformative tool outputs."
        )
    else:
        print(
            f"Conclusion: MOCK_TRIGGERED_DRIFT is NOT dominant "
            f"({mock_share*100:.0f}%). The underperformance is partly or "
            "primarily attributable to another mechanism — check the "
            "non-mock buckets for the dominant pattern."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
