from __future__ import annotations

"""Verify GitHub tools work end-to-end and the 25 hand-crafted
benchmark tasks load cleanly.

Three parts:
  1. Live sanity check of each of the 5 tools against a known target
     (torvalds/linux for the four repo-specific tools, 'machine learning'
     for search).
  2. Print every task in ``benchmarks/github/tasks.json`` so the gold
     answers can be spot-checked by eye.
  3. Print the category distribution
     (embarrassingly_parallel / mixed / sequential).

Run:

    python scripts/verify_github_benchmark.py
"""

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.tools.github import (  # noqa: E402
    GITHUB_TOOLS,
    github_get_latest_release,
    github_get_open_issues_count,
    github_get_repo,
    github_get_top_contributors,
    github_search_repos,
)

TASKS_PATH = REPO_ROOT / "benchmarks" / "github" / "tasks.json"


def _print_blob(label: str, value) -> None:
    print(f"\n{label}:")
    if isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(f"  → {value}")


async def part_1_tool_sanity_checks() -> None:
    print("=" * 78)
    print("Part 1 · Live tool sanity checks")
    print("=" * 78)
    auth = (
        "(authenticated via GITHUB_TOKEN — 5000 req/hr)"
        if os.environ.get("GITHUB_TOKEN")
        else "(unauthenticated — 60 req/hr cap)"
    )
    print(f"Mode: {auth}")
    print(f"Tools registered in GITHUB_TOOLS: {[t.name for t in GITHUB_TOOLS]}")

    _print_blob(
        "github_get_repo('torvalds', 'linux')",
        await github_get_repo("torvalds", "linux"),
    )
    _print_blob(
        "github_get_latest_release('torvalds', 'linux')",
        await github_get_latest_release("torvalds", "linux"),
    )
    _print_blob(
        "github_get_top_contributors('torvalds', 'linux', n=5)",
        await github_get_top_contributors("torvalds", "linux", n=5),
    )
    _print_blob(
        "github_get_open_issues_count('torvalds', 'linux')",
        await github_get_open_issues_count("torvalds", "linux"),
    )
    _print_blob(
        "github_search_repos('machine learning', n=5)",
        await github_search_repos("machine learning", n=5),
    )


def part_2_print_all_tasks(tasks: list[dict]) -> None:
    print()
    print("=" * 78)
    print(f"Part 2 · All {len(tasks)} benchmark tasks (questions + gold answers)")
    print("=" * 78)
    for t in tasks:
        cat = t.get("category", "?")
        print(
            f"\n[{t['id']}]  {cat}  "
            f"(answer_type={t.get('answer_type')}, "
            f"expected_parallel_count={t.get('expected_parallel_count')})"
        )
        print(f"  Q:      {t['question']}")
        print(f"  Gold:   {t['answer']!r}")
        notes = t.get("notes")
        if notes:
            print(f"  Notes:  {notes}")


def part_3_distribution(tasks: list[dict]) -> None:
    print()
    print("=" * 78)
    print("Part 3 · Task category distribution")
    print("=" * 78)
    by_cat: Counter[str] = Counter(t.get("category", "unknown") for t in tasks)
    for cat in ("embarrassingly_parallel", "mixed", "sequential"):
        print(f"  {cat:>24}: {by_cat[cat]}")
    extras = {c for c in by_cat if c not in {"embarrassingly_parallel", "mixed", "sequential"}}
    for cat in sorted(extras):
        print(f"  {cat:>24}: {by_cat[cat]}  (unexpected category)")
    print(f"  {'TOTAL':>24}: {sum(by_cat.values())}")

    # Also helpful: expected_parallel_count distribution
    print()
    print("expected_parallel_count distribution:")
    pc: Counter[int] = Counter(int(t.get("expected_parallel_count", 0)) for t in tasks)
    for n in sorted(pc):
        print(f"  {n:>2}: {pc[n]} task(s)")


async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")

    if not TASKS_PATH.exists():
        print(f"ERROR: tasks file missing at {TASKS_PATH}", file=sys.stderr)
        return 1
    with open(TASKS_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    await part_1_tool_sanity_checks()
    part_2_print_all_tasks(tasks)
    part_3_distribution(tasks)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
