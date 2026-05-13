from __future__ import annotations

"""Categorize every failed task in ``results/results.json`` into one of
five failure modes and emit a per-strategy breakdown table.

Categories (in priority order — first match wins):

  1. ``PLAN_VALIDATION_ERROR`` — predicted answer starts with
     ``DAG_PLANNER_EMPTY_RESULT:``.
  2. ``JUDGE_DISPUTED`` — predicted answer contains the gold answer as a
     substring (case-insensitive) but the judge marked it wrong. This is
     a genuine disagreement between the predicted text and the judge's
     semantic interpretation.
  3. ``HEDGED_DESPITE_EVIDENCE`` — predicted answer matches a refusal
     pattern AND we have indirect evidence the gold WAS retrievable
     (currently always False for non-traced strategies; see note below).
  4. ``HEDGED_REFUSAL`` — predicted answer matches a refusal pattern
     (e.g. "I cannot find", "no information," "unable to determine").
  5. ``WRONG_FIRST_RETRIEVAL`` — none of the above, and the predicted
     answer mentions an entity that doesn't match the question framing.
     Heuristic: gold is NOT contained anywhere in the predicted text.
  6. ``OTHER`` — fallback.

Note on ``HEDGED_DESPITE_EVIDENCE``: detecting whether the gold appeared
in any retrieved tool output requires per-task traces we don't persist
in ``results.json``. The category is wired up for completeness; without
trace data it stays empty and rolls up into plain ``HEDGED_REFUSAL``.

Output: per-strategy percentage table written to
``results/failure_modes.md`` (and printed to stdout).

Run:

    python scripts/analyze_failures.py
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "results" / "results.json"
OUTPUT_PATH = REPO_ROOT / "results" / "failure_modes.md"

REFUSAL_PATTERNS: tuple[str, ...] = (
    "i cannot find",
    "i cannot answer",
    "i can't find",
    "i can't answer",
    "no information",
    "unable to determine",
    "unable to find",
    "the provided information does not contain",
    "the provided results do not",
    "the provided text does not",
    "the provided search results do not",
    "based on the available information",
    "based on the provided",
    "does not contain",
    "do not contain",
    "is not ascertainable",
    "not enough information",
)

CATEGORIES: list[str] = [
    "PLAN_VALIDATION_ERROR",
    "JUDGE_DISPUTED",
    "HEDGED_DESPITE_EVIDENCE",
    "HEDGED_REFUSAL",
    "WRONG_FIRST_RETRIEVAL",
    "OTHER",
]


def _looks_like_refusal(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in REFUSAL_PATTERNS)


def _categorize(record: dict[str, Any]) -> str:
    pred = (record.get("predicted_answer") or "").strip()
    gold = (record.get("gold_answer") or "").strip()
    if not pred:
        return "OTHER"

    # 1. Plan validation error sentinel.
    if pred.startswith("DAG_PLANNER_EMPTY_RESULT:"):
        return "PLAN_VALIDATION_ERROR"

    pred_lower = pred.lower()
    gold_lower = gold.lower()
    gold_in_pred = bool(gold_lower) and gold_lower in pred_lower

    # 2. Judge disputed: gold appears verbatim in prediction but marked wrong.
    if gold_in_pred:
        return "JUDGE_DISPUTED"

    # 3 & 4. Hedged refusal.
    if _looks_like_refusal(pred):
        # We don't have per-task tool outputs in results.json; without that
        # we can't distinguish HEDGED_DESPITE_EVIDENCE from plain
        # HEDGED_REFUSAL. Fall through to HEDGED_REFUSAL.
        return "HEDGED_REFUSAL"

    # 5. Wrong-first-retrieval heuristic: gold not anywhere in pred.
    if gold and gold_lower not in pred_lower:
        return "WRONG_FIRST_RETRIEVAL"

    return "OTHER"


def _dedupe(records: list[dict]) -> list[dict]:
    """Keep latest row per (strategy, benchmark, seed, task_id)."""
    latest: dict[tuple, dict] = {}
    for r in records:
        key = (
            r.get("strategy"),
            r.get("benchmark"),
            r.get("seed"),
            r.get("task_id"),
        )
        if not all(k is not None for k in key):
            continue
        latest[key] = r
    return list(latest.values())


def main() -> int:
    if not RESULTS_PATH.exists():
        print(f"ERROR: {RESULTS_PATH} missing.", file=sys.stderr)
        return 1
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
    records = _dedupe(records)

    # Per-strategy: count failures by category.
    by_strategy: dict[str, Counter[str]] = defaultdict(Counter)
    totals: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    for r in records:
        strat = r.get("strategy")
        if strat is None:
            continue
        totals[strat] += 1
        if r.get("judge_correct"):
            continue
        failures[strat] += 1
        by_strategy[strat][_categorize(r)] += 1

    # ----- Render markdown ------------------------------------------------
    strategies = sorted(by_strategy.keys())
    lines: list[str] = []
    lines.append("# Failure-mode breakdown")
    lines.append("")
    lines.append(
        "Each cell is the **percentage of that strategy's failures** "
        "falling into the named category. Rightmost column is the total "
        "failure count (over all benchmarks × seeds, deduped to latest row "
        "per task)."
    )
    lines.append("")
    header = "| Strategy | " + " | ".join(CATEGORIES) + " | Failures | Tasks |"
    sep = "| --- | " + " | ".join(["---"] * len(CATEGORIES)) + " | --- | --- |"
    lines.append(header)
    lines.append(sep)
    for strat in strategies:
        total_fail = failures[strat]
        total_tasks = totals[strat]
        cells = []
        for cat in CATEGORIES:
            count = by_strategy[strat][cat]
            pct = (count / total_fail * 100.0) if total_fail else 0.0
            cells.append(f"{pct:.1f}% ({count})" if count else "—")
        lines.append(
            f"| {strat} | "
            + " | ".join(cells)
            + f" | {total_fail} | {total_tasks} |"
        )

    md = "\n".join(lines) + "\n"

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\nSaved to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
