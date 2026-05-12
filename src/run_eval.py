from __future__ import annotations

"""End-to-end eval harness — Weekend 1 milestone.

CLI:

    python -m src.run_eval --strategy react --benchmark hotpotqa --n 30

For each task: run the chosen strategy, then judge the prediction, then
record metrics. Tasks run concurrently under an :class:`asyncio.Semaphore`
cap (default 3, sized to the Gemini AI Studio free-tier 15-RPM budget for a
ReAct loop that emits ~5 LLM calls per task plus 1 judge call). A single
task failing never kills the run — its row is saved with ``error`` set so
the failure is visible in the eval.

Per-task records are *appended* to the output JSON (default
``results/results.json``), so successive invocations build up the
strategy × benchmark comparison matrix.

See SPEC.md § 3 Step 6.
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import traceback
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from src.judge import judge_answer
from src.llm.base import LLMProvider
from src.llm.gemini import GeminiProvider
from src.metrics import AggregateMetrics
from src.strategies.dag_planner import run_dag_planner
from src.strategies.native_parallel import run_native_parallel
from src.strategies.react import run_react
from src.tools.base import Tool
from src.tools.github import GITHUB_TOOLS
from src.tools.wikipedia import WIKIPEDIA_TOOLS

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT: Path = REPO_ROOT / "results" / "results.json"

# Strategy registry. Steps 7 and 8 plug in native_parallel and dag_planner.
StrategyFn = Callable[..., Awaitable[tuple[str, AggregateMetrics]]]
STRATEGIES: dict[str, StrategyFn] = {
    "react": run_react,
    "native_parallel": run_native_parallel,
    "dag_planner": run_dag_planner,
}

BENCHMARK_PATHS: dict[str, Path] = {
    "hotpotqa": REPO_ROOT / "benchmarks" / "hotpotqa" / "tasks.json",
    "github": REPO_ROOT / "benchmarks" / "github" / "tasks.json",
}

# Each benchmark uses ONLY its own tool set — Wikipedia tools never leak
# into a GitHub task and vice versa. Strategies receive the per-benchmark
# slice via the dispatch in run_eval().
TOOLS_FOR_BENCHMARK: dict[str, list[Tool]] = {
    "hotpotqa": WIKIPEDIA_TOOLS,
    "github": GITHUB_TOOLS,
}


# -----------------------------------------------------------------------------
# Metrics ↔ dict
# -----------------------------------------------------------------------------
def _empty_metrics_dict() -> dict[str, Any]:
    return {
        "n_llm_calls": 0,
        "n_tool_calls": 0,
        "n_tools_executed": 0,
        "discarded_parallel_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "total_wall_clock_seconds": 0.0,
    }


def _metrics_to_dict(m: AggregateMetrics) -> dict[str, Any]:
    return {
        "n_llm_calls": m.n_llm_calls,
        "n_tool_calls": m.n_tool_calls,
        "n_tools_executed": m.n_tools_executed,
        "discarded_parallel_calls": m.discarded_parallel_calls,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "cost_usd": m.cost_usd,
        "total_wall_clock_seconds": m.total_wall_clock_seconds,
    }


# -----------------------------------------------------------------------------
# Per-task runner
# -----------------------------------------------------------------------------
async def _run_one_task(
    task: dict[str, Any],
    strategy_name: str,
    strategy_fn: StrategyFn,
    tools: list[Tool],
    llm: LLMProvider,
    benchmark: str,
    sem: asyncio.Semaphore,
    console: Console,
) -> dict[str, Any]:
    """Execute strategy + judge on one task, returning the result record."""
    async with sem:
        record: dict[str, Any] = {
            "task_id": task["id"],
            "strategy": strategy_name,
            "benchmark": benchmark,
            "question": task["question"],
            "gold_answer": task["answer"],
            "predicted_answer": "",
            "judge_correct": False,
            "judge_rationale": "",
            "metrics": _empty_metrics_dict(),
            "error": None,
        }
        # Pass-through fields from the benchmark (currently only present
        # on GitHub tasks; HotpotQA omits them and the judge defaults
        # back to its original HotpotQA-shaped behavior).
        if "answer_type" in task:
            record["answer_type"] = task["answer_type"]
        if "category" in task:
            record["category"] = task["category"]
        try:
            predicted, metrics = await strategy_fn(
                question=task["question"],
                tools=tools,
                llm=llm,
            )
            record["predicted_answer"] = predicted
            record["metrics"] = _metrics_to_dict(metrics)

            verdict = await judge_answer(
                question=task["question"],
                gold=task["answer"],
                predicted=predicted,
                llm=llm,
                answer_type=task.get("answer_type"),
            )
            record["judge_correct"] = bool(verdict.get("correct", False))
            record["judge_rationale"] = verdict.get("rationale", "")

            mark = "[green]✓[/green]" if record["judge_correct"] else "[red]✗[/red]"
            console.print(
                f"  {mark} {task['id']}  "
                f"({metrics.n_llm_calls} llm / {metrics.n_tool_calls} tool calls, "
                f"{metrics.total_wall_clock_seconds:.1f}s, "
                f"${metrics.cost_usd:.4f})  "
                f"pred=[italic]{(predicted or '(empty)')[:60]}[/italic]"
            )
        except Exception as exc:  # noqa: BLE001 — keep the run alive
            record["error"] = f"{type(exc).__name__}: {exc}"
            console.print(
                f"  [bold red]![/bold red] {task['id']}  "
                f"ERROR: {record['error']}",
                style="red",
            )
            traceback.print_exc()
        return record


# -----------------------------------------------------------------------------
# Aggregation + IO
# -----------------------------------------------------------------------------
def _percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1)))))
    return s[idx]


def _mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _print_summary(
    records: list[dict[str, Any]],
    strategy: str,
    benchmark: str,
    console: Console,
) -> None:
    n = len(records)
    successful = [r for r in records if r["error"] is None]
    n_errors = n - len(successful)
    n_correct = sum(1 for r in records if r["judge_correct"])
    accuracy_pct = (n_correct / n * 100.0) if n else 0.0

    latencies = [r["metrics"]["total_wall_clock_seconds"] for r in successful]
    in_toks = [r["metrics"]["input_tokens"] for r in successful]
    out_toks = [r["metrics"]["output_tokens"] for r in successful]
    costs = [r["metrics"]["cost_usd"] for r in successful]
    llm_calls = [r["metrics"]["n_llm_calls"] for r in successful]
    tool_calls = [r["metrics"]["n_tool_calls"] for r in successful]
    tools_exec = [r["metrics"].get("n_tools_executed", 0) for r in successful]
    discards = sum(r["metrics"]["discarded_parallel_calls"] for r in successful)

    table = Table(title="Run summary", show_header=False, title_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Strategy / Benchmark", f"{strategy} / {benchmark}")
    table.add_row("Tasks", str(n))
    table.add_row(
        "Accuracy",
        f"[bold]{n_correct}/{n}[/bold] ({accuracy_pct:.1f}%)",
    )
    table.add_row(
        "Latency p50 / p95 / mean",
        f"{_percentile(latencies, 50):.1f}s / "
        f"{_percentile(latencies, 95):.1f}s / "
        f"{_mean(latencies):.1f}s",
    )
    table.add_row(
        "Mean tokens (in / out)",
        f"{_mean(in_toks):.0f} / {_mean(out_toks):.0f}",
    )
    table.add_row("Mean cost per task", f"${_mean(costs):.4f}")
    table.add_row("Total cost", f"${sum(costs):.4f}")
    table.add_row("Mean LLM calls per task", f"{_mean(llm_calls):.2f}")
    table.add_row("Mean LLM tool calls per task", f"{_mean(tool_calls):.2f}")
    table.add_row("Mean tools executed per task", f"{_mean(tools_exec):.2f}")
    table.add_row("Discarded parallel calls (total)", str(discards))
    table.add_row(
        "Errors",
        f"[red]{n_errors}[/red]" if n_errors else str(n_errors),
    )

    console.print()
    console.print(table)


def _load_existing(path: Path) -> list[dict[str, Any]]:
    """Read existing results array. Tolerates a missing or corrupt file."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _save_results(path: Path, new_records: list[dict[str, Any]]) -> int:
    """Append ``new_records`` to ``path``; returns the new total row count."""
    existing = _load_existing(path)
    combined = existing + new_records
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    return len(combined)


# -----------------------------------------------------------------------------
# Orchestration
# -----------------------------------------------------------------------------
async def run_eval(
    strategy: str,
    benchmark: str,
    n: int,
    output: Path,
    concurrency: int,
) -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set.", file=sys.stderr)
        return 1

    tasks_path = BENCHMARK_PATHS[benchmark]
    if not tasks_path.exists():
        print(
            f"ERROR: tasks file missing at {tasks_path}.\n"
            f"       Run `python -m benchmarks.{benchmark}.load` first.",
            file=sys.stderr,
        )
        return 3

    with open(tasks_path, "r", encoding="utf-8") as f:
        all_tasks = json.load(f)
    tasks_to_run = all_tasks if n <= 0 else all_tasks[:n]

    strategy_fn = STRATEGIES[strategy]
    tools = TOOLS_FOR_BENCHMARK[benchmark]
    llm = GeminiProvider()

    console = Console()
    console.print(
        f"Running [bold]{strategy}[/bold] on [bold]{benchmark}[/bold] — "
        f"{len(tasks_to_run)} task(s), concurrency={concurrency}, "
        f"model={llm.model}\n"
    )

    sem = asyncio.Semaphore(concurrency)
    coros = [
        _run_one_task(
            task=t,
            strategy_name=strategy,
            strategy_fn=strategy_fn,
            tools=tools,
            llm=llm,
            benchmark=benchmark,
            sem=sem,
            console=console,
        )
        for t in tasks_to_run
    ]
    new_records = await asyncio.gather(*coros)

    total_rows = _save_results(output, new_records)
    console.print(
        f"\nAppended {len(new_records)} task row(s) to "
        f"[bold]{output}[/bold] (total rows now: {total_rows})."
    )

    _print_summary(new_records, strategy, benchmark, console)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a strategy × benchmark eval and append results to JSON."
    )
    parser.add_argument(
        "--strategy",
        required=True,
        choices=list(STRATEGIES),
        help="Which strategy to run.",
    )
    parser.add_argument(
        "--benchmark",
        required=True,
        choices=list(BENCHMARK_PATHS),
        help="Which benchmark to run against.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=30,
        help="How many tasks to evaluate (0 = all available).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to append per-task result records (JSON array).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Max tasks running in parallel. Respects Gemini's 15 RPM cap.",
    )
    args = parser.parse_args(argv)
    return asyncio.run(
        run_eval(
            strategy=args.strategy,
            benchmark=args.benchmark,
            n=args.n,
            output=args.output,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
