from __future__ import annotations

"""Backfill ``llm`` field on existing ``results/results.json`` rows.

Weekend 3 added a ``--llm {gemini,claude}`` flag and stamps every new
record with its provider. Every pre-Weekend-3 row was generated with
Gemini — this script idempotently fills in ``llm="gemini"`` on any row
missing the field, so cross-LLM slicing in ``aggregate_results.py``
groups uniformly.

Idempotent: rows already carrying ``llm`` are left alone.

Run:

    python scripts/backfill_llm_field.py
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "results" / "results.json"


def main() -> int:
    if not RESULTS_PATH.exists():
        print(f"No results file at {RESULTS_PATH}; nothing to do.")
        return 0

    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    n_total = len(records)
    n_backfilled = 0
    for r in records:
        if "llm" not in r:
            r["llm"] = "gemini"
            n_backfilled += 1

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Backfilled llm=gemini on {n_backfilled}/{n_total} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
