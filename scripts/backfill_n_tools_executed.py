from __future__ import annotations

"""One-off backfill for ``metrics.n_tools_executed`` on existing
``results/results.json`` rows.

Why: ``n_tools_executed`` was added after the 30-task ReAct and
native_parallel runs. To avoid burning API quota re-running them, we
infer the value from the existing data:

  * ``react``:           ``n_tool_calls - discarded_parallel_calls``
                         (executions = emitted minus dropped)
  * ``native_parallel``: ``n_tool_calls``
                         (every emitted call is executed; nothing dropped)
  * other strategies:    cannot infer — leave the row alone

Rows that already carry ``n_tools_executed`` are skipped (idempotent).

Run:

    python scripts/backfill_n_tools_executed.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "results" / "results.json"


def _infer(
    strategy: str, n_tool_calls: int, discarded: int
) -> Optional[int]:
    """Return the inferred value, or ``None`` if we cannot infer."""
    if strategy == "react":
        return max(0, n_tool_calls - discarded)
    if strategy == "native_parallel":
        return n_tool_calls
    return None


def main() -> int:
    if not RESULTS_PATH.exists():
        print(f"ERROR: {RESULTS_PATH} doesn't exist.", file=sys.stderr)
        return 1

    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not isinstance(records, list):
        print(
            f"ERROR: {RESULTS_PATH} is not a JSON array (got "
            f"{type(records).__name__}).",
            file=sys.stderr,
        )
        return 2

    totals: dict[str, int] = defaultdict(int)
    by_strategy: dict[str, dict[str, int]] = defaultdict(
        lambda: {"updated": 0, "already_set": 0, "could_not_infer": 0}
    )

    for record in records:
        strategy = record.get("strategy", "?")
        metrics = record.setdefault("metrics", {})

        if "n_tools_executed" in metrics:
            totals["already_set"] += 1
            by_strategy[strategy]["already_set"] += 1
            continue

        inferred = _infer(
            strategy=strategy,
            n_tool_calls=int(metrics.get("n_tool_calls", 0)),
            discarded=int(metrics.get("discarded_parallel_calls", 0)),
        )

        if inferred is None:
            totals["could_not_infer"] += 1
            by_strategy[strategy]["could_not_infer"] += 1
            continue

        metrics["n_tools_executed"] = inferred
        totals["updated"] += 1
        by_strategy[strategy]["updated"] += 1

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Backfilled {RESULTS_PATH}")
    print(f"  total rows       : {len(records)}")
    print(f"  updated          : {totals['updated']}")
    print(f"  already had it   : {totals['already_set']}")
    print(f"  could not infer  : {totals['could_not_infer']}")
    if by_strategy:
        print()
        print("By strategy:")
        for strategy in sorted(by_strategy):
            s = by_strategy[strategy]
            print(
                f"  {strategy:>18}: "
                f"updated={s['updated']:3d}  "
                f"already_set={s['already_set']:3d}  "
                f"could_not_infer={s['could_not_infer']:3d}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
