from __future__ import annotations

"""Aggregate ``results/results.json`` into per-cell mean ± stddev tables
grouped by (strategy, benchmark, seed).

The mean and stddev are computed across SEEDS, not across tasks within a
seed. That is: for each (strategy, benchmark) cell we first compute the
per-seed scalar (e.g. accuracy for that seed's 30-task run), then take
``mean ± stdev`` over the seeds.

For strategies / benchmarks that have only one seed in the data, the
stddev column reports ``±—``.

Output: a markdown report written to
``results/results_with_ci.md`` (and also printed to stdout) covering all
benchmarks present in the dataset, plus a section listing pairwise
strategy comparisons whose mean-to-mean gap is at least 2 × the wider
of the two stddevs (the SPEC's "statistically meaningful" bar).

Run:

    python scripts/aggregate_results.py
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "results" / "results.json"
OUTPUT_PATH = REPO_ROOT / "results" / "results_with_ci.md"

STRATEGY_ORDER = ["react", "native_parallel", "dag_planner"]
STRATEGY_DISPLAY = {
    "react": "ReAct",
    "native_parallel": "Native parallel",
    "dag_planner": "DAG planner",
}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def _per_seed_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    """Reduce a single seed's rows to scalar metrics."""
    n = len(records)
    if n == 0:
        return {}
    correct = sum(1 for r in records if r.get("judge_correct"))
    successful = [r for r in records if r.get("error") is None]

    def _mean(field: str) -> float:
        vals = [r["metrics"][field] for r in successful if "metrics" in r]
        return statistics.mean(vals) if vals else 0.0

    def _p50_latency() -> float:
        vals = sorted(
            r["metrics"]["total_wall_clock_seconds"]
            for r in successful
            if "metrics" in r
        )
        if not vals:
            return 0.0
        return vals[len(vals) // 2]

    return {
        "n_tasks": float(n),
        "accuracy_pct": (correct / n) * 100.0,
        "llm_calls": _mean("n_llm_calls"),
        "tools_executed": _mean("n_tools_executed"),
        "cost_usd": _mean("cost_usd"),
        "p50_latency_s": _p50_latency(),
        "wall_clock_mean_s": _mean("total_wall_clock_seconds"),
        "errors": float(n - len(successful)),
    }


def _mean_std(values: list[float]) -> tuple[float, Optional[float]]:
    if not values:
        return 0.0, None
    if len(values) == 1:
        return values[0], None
    return statistics.mean(values), statistics.stdev(values)


def _aggregate(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
    """Bucket by (benchmark, strategy) → metric → {seeds, mean, std}.

    Each metric value is the aggregate across seeds of per-seed scalars.
    """
    # Dedupe by (strategy, benchmark, seed, task_id): keep the LATEST row.
    # Early dev iterations re-ran some cells (e.g. dag_planner/hotpotqa/seed=42
    # was re-run after Step-8 bug fixes; verify_step6 also appended 3 tasks
    # to react/hotpotqa/seed=42). The canonical accuracy is the most recent
    # full-run row for each task.
    latest_by_cell_task: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for r in rows:
        bm = r.get("benchmark")
        st = r.get("strategy")
        sd = r.get("seed")
        tid = r.get("task_id")
        if not bm or not st or sd is None or not tid:
            continue
        latest_by_cell_task[(bm, st, int(sd), tid)] = r  # later rows overwrite

    by_cell_seed: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for (bm, st, sd, _tid), r in latest_by_cell_task.items():
        by_cell_seed[(bm, st, sd)].append(r)

    # First reduce per-seed
    by_cell: dict[tuple[str, str], dict[int, dict[str, float]]] = defaultdict(dict)
    for (bm, st, sd), recs in by_cell_seed.items():
        by_cell[(bm, st)][sd] = _per_seed_metrics(recs)

    # Then aggregate across seeds
    result: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for cell, per_seed in by_cell.items():
        seeds = sorted(per_seed)
        cell_summary: dict[str, dict[str, Any]] = {"_seeds": {"seeds": seeds}}
        for metric in (
            "n_tasks",
            "accuracy_pct",
            "llm_calls",
            "tools_executed",
            "cost_usd",
            "p50_latency_s",
            "wall_clock_mean_s",
            "errors",
        ):
            values = [per_seed[s][metric] for s in seeds if metric in per_seed[s]]
            mean, std = _mean_std(values)
            cell_summary[metric] = {
                "mean": mean,
                "std": std,
                "per_seed": {s: per_seed[s].get(metric) for s in seeds},
            }
        result[cell] = cell_summary
    return result


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def _fmt_pct(mean: float, std: Optional[float]) -> str:
    if std is None:
        return f"{mean:.1f}% ± —"
    return f"{mean:.1f}% ± {std:.1f}pp"


def _fmt_num(mean: float, std: Optional[float], digits: int = 2) -> str:
    if std is None:
        return f"{mean:.{digits}f} ± —"
    return f"{mean:.{digits}f} ± {std:.{digits}f}"


def _fmt_cost(mean: float, std: Optional[float]) -> str:
    if std is None:
        return f"${mean:.4f} ± —"
    return f"${mean:.4f} ± ${std:.4f}"


def _fmt_secs(mean: float, std: Optional[float]) -> str:
    if std is None:
        return f"{mean:.2f}s ± —"
    return f"{mean:.2f}s ± {std:.2f}s"


BENCHMARK_TITLE = {
    "hotpotqa": "HotpotQA (bridge — adaptive 2-hop)",
    "hotpotqa_comparison": "HotpotQA (comparison — inherently parallel)",
    "github": "GitHub (structurally predictable multi-entity)",
}
BENCHMARK_ORDER = ["hotpotqa", "hotpotqa_comparison", "github"]


def render_markdown(agg: dict[tuple[str, str], dict[str, dict[str, Any]]]) -> str:
    lines: list[str] = []
    lines.append("# Multi-seed eval — mean ± stddev across seeds")
    lines.append("")
    lines.append(
        "Each cell aggregates per-seed scalars (one accuracy / mean-LLM-calls "
        "etc. per seed) across seeds. Stddev is the sample stddev of those "
        "per-seed values — not the within-seed variance. `±—` means only "
        "one seed is present."
    )
    lines.append("")

    benchmarks_present = sorted(
        {bm for bm, _ in agg.keys()},
        key=lambda b: (BENCHMARK_ORDER.index(b) if b in BENCHMARK_ORDER else 99, b),
    )

    for bm in benchmarks_present:
        title = BENCHMARK_TITLE.get(bm, bm)
        lines.append(f"## {title}")
        lines.append("")
        # Build the seed-list note from any cell
        seeds_used: list[int] = []
        n_tasks_used: list[int] = []
        for st in STRATEGY_ORDER:
            cell = agg.get((bm, st))
            if cell:
                seeds_used = cell["_seeds"]["seeds"]
                n_tasks_used = list(cell["n_tasks"]["per_seed"].values())
                break
        if seeds_used:
            ns = sorted({int(v) for v in n_tasks_used})
            lines.append(
                f"_Seeds: {seeds_used}; n per seed: {ns[0] if len(ns) == 1 else ns}._"
            )
            lines.append("")

        cols = [STRATEGY_DISPLAY[s] for s in STRATEGY_ORDER if (bm, s) in agg]
        if not cols:
            lines.append("_(no data)_")
            lines.append("")
            continue

        # Markdown table
        header = "| Metric | " + " | ".join(cols) + " |"
        sep = "| --- | " + " | ".join(["---"] * len(cols)) + " |"
        lines.append(header)
        lines.append(sep)

        def row(label: str, fmt_fn, metric: str) -> None:
            cells = []
            for s in STRATEGY_ORDER:
                if (bm, s) not in agg:
                    continue
                m = agg[(bm, s)][metric]
                cells.append(fmt_fn(m["mean"], m["std"]))
            lines.append(f"| {label} | " + " | ".join(cells) + " |")

        row("Accuracy", _fmt_pct, "accuracy_pct")
        row("LLM calls / task", _fmt_num, "llm_calls")
        row("Tools executed / task", _fmt_num, "tools_executed")
        row("Cost / task", _fmt_cost, "cost_usd")
        row("Wall-clock p50", _fmt_secs, "p50_latency_s")
        row("Wall-clock mean", _fmt_secs, "wall_clock_mean_s")
        row("Errors (total)", lambda m, s: _fmt_num(m, s, digits=1), "errors")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Meaningfulness section
# ---------------------------------------------------------------------------
def _meaningful_pairs(
    agg: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> str:
    lines: list[str] = []
    lines.append("## Statistically meaningful differences")
    lines.append("")
    lines.append(
        "A pairwise gap is flagged **MEANINGFUL** when "
        "`|mean_a − mean_b| ≥ 2 × max(stddev_a, stddev_b)` — i.e. the two "
        "means are at least 2 stddevs apart on the wider of the two error "
        "bars. Cells with only one seed are skipped (no stddev defined)."
    )
    lines.append("")

    metric_specs = [
        ("accuracy_pct", "Accuracy", "pp"),
        ("llm_calls", "LLM calls / task", ""),
        ("tools_executed", "Tools executed / task", ""),
        ("cost_usd", "Cost / task", " USD"),
        ("p50_latency_s", "Wall-clock p50", "s"),
    ]
    benchmarks_present = sorted(
        {bm for bm, _ in agg.keys()},
        key=lambda b: (BENCHMARK_ORDER.index(b) if b in BENCHMARK_ORDER else 99, b),
    )

    for bm in benchmarks_present:
        title = BENCHMARK_TITLE.get(bm, bm)
        present_strategies = [s for s in STRATEGY_ORDER if (bm, s) in agg]
        lines.append(f"### {title}")
        lines.append("")
        any_emitted = False
        for metric, label, unit in metric_specs:
            for i, sa in enumerate(present_strategies):
                for sb in present_strategies[i + 1 :]:
                    a = agg[(bm, sa)][metric]
                    b = agg[(bm, sb)][metric]
                    if a["std"] is None or b["std"] is None:
                        continue
                    gap = abs(a["mean"] - b["mean"])
                    bar = 2 * max(a["std"], b["std"])
                    if bar == 0:
                        flag = "MEANINGFUL (zero stddev on one side)" if gap > 0 else "tied"
                    elif gap >= bar:
                        flag = f"**MEANINGFUL** ({gap / max(a['std'], b['std']):.1f}× max stddev)"
                    else:
                        flag = f"marginal ({gap / max(a['std'], b['std']):.1f}× max stddev)"
                    if "MEANINGFUL" not in flag and "tied" not in flag:
                        continue  # only print meaningful + tied; marginals omitted
                    if "cost" in metric:
                        a_str, b_str = f"${a['mean']:.4f}", f"${b['mean']:.4f}"
                        gap_str = f"${gap:.4f}"
                        sig_str = f"${max(a['std'], b['std']):.4f}"
                        unit_a = unit_b = ""  # the leading $ replaces the unit
                    elif "pct" in metric or "latency" in metric or "wall" in metric:
                        a_str, b_str = f"{a['mean']:.1f}", f"{b['mean']:.1f}"
                        gap_str = f"{gap:.2f}"
                        sig_str = f"{max(a['std'], b['std']):.2f}"
                        unit_a = unit_b = unit
                    else:
                        a_str, b_str = f"{a['mean']:.2f}", f"{b['mean']:.2f}"
                        gap_str = f"{gap:.2f}"
                        sig_str = f"{max(a['std'], b['std']):.2f}"
                        unit_a = unit_b = unit
                    lines.append(
                        f"- **{label}**: "
                        f"{STRATEGY_DISPLAY[sa]} ({a_str}{unit_a}) vs "
                        f"{STRATEGY_DISPLAY[sb]} ({b_str}{unit_b}) — "
                        f"gap {gap_str}{unit}, max σ {sig_str}{unit} → {flag}"
                    )
                    any_emitted = True
        if not any_emitted:
            lines.append("_No pairwise differences reach the 2σ bar on the wider stddev._")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    if not RESULTS_PATH.exists():
        print(f"ERROR: {RESULTS_PATH} doesn't exist.", file=sys.stderr)
        return 1
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
    if not isinstance(records, list):
        print(f"ERROR: {RESULTS_PATH} is not a JSON array.", file=sys.stderr)
        return 2

    agg = _aggregate(records)
    md = render_markdown(agg) + "\n" + _meaningful_pairs(agg)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(md)

    print(md)
    print(f"\nSaved to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
