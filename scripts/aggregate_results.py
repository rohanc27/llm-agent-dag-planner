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
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

# Bootstrap configuration. Deterministic seed so re-running the aggregator
# produces stable CI bounds; 1000 resamples per cell is enough for 2 d.p.
# percentile estimates and keeps the script <2 s on the full results set.
_BOOTSTRAP_N: int = 1000
_BOOTSTRAP_SEED: int = 0xB007

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "results" / "results.json"
OUTPUT_PATH = REPO_ROOT / "results" / "results_with_ci.md"

STRATEGY_ORDER = [
    "react",
    "native_parallel",
    "dag_planner",
    "dag_replan_cap2",
    "dag_replan_cap5",
    "dag_replan_cap2_empty",
    "dag_replan_cap5_empty",
    "dag_replan_cap2_empty_top3",
    "dag_replan_cap5_empty_top3",
    "dag_replan_aggressive",
    "dag_replan_max",
    "dag_replan_aggressive_no_diversify",
    "dag_replan_aggressive_no_cot",
    "dag_replan_aggressive_no_topk",
    "dag_replan_aggressive_no_emptysynth",
]
STRATEGY_DISPLAY = {
    "react": "ReAct",
    "native_parallel": "Native parallel",
    "dag_planner": "DAG planner",
    "dag_replan_cap2": "DAG replan ×2 (any_failure)",
    "dag_replan_cap5": "DAG replan ×5 (any_failure)",
    "dag_replan_cap2_empty": "DAG replan ×2 (empty_synth)",
    "dag_replan_cap5_empty": "DAG replan ×5 (empty_synth)",
    "dag_replan_cap2_empty_top3": "DAG replan ×2 (empty_synth, top-3)",
    "dag_replan_cap5_empty_top3": "DAG replan ×5 (empty_synth, top-3)",
    "dag_replan_aggressive": "DAG replan aggressive (cap=5, diversif+CoT)",
    "dag_replan_max": "DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT)",
    "dag_replan_aggressive_no_diversify": "aggressive − diversification",
    "dag_replan_aggressive_no_cot": "aggressive − CoT",
    "dag_replan_aggressive_no_topk": "aggressive − top-K (back to top-1)",
    "dag_replan_aggressive_no_emptysynth": "aggressive − empty_synth (back to any_failure)",
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
        vals = [
            r["metrics"].get(field, 0) for r in successful if "metrics" in r
        ]
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
        "replans": _mean("n_replans"),
        "cost_usd": _mean("cost_usd"),
        "p50_latency_s": _p50_latency(),
        "wall_clock_mean_s": _mean("total_wall_clock_seconds"),
        "errors": float(n - len(successful)),
        # Keep the raw 0/1 correctness vector for bootstrap CI computation.
        "_correctness_vector": [
            1 if r.get("judge_correct") else 0 for r in records
        ],
    }


def _bootstrap_ci_pct(
    correctness: list[int], n_resamples: int = _BOOTSTRAP_N
) -> tuple[float, float]:
    """Return (2.5th, 97.5th) percentile of bootstrap-resampled accuracy.

    Resamples ``correctness`` with replacement to the same size,
    computes the proportion correct on each resample, and reads the
    2.5%/97.5% quantiles. Returns ``(0.0, 0.0)`` for empty inputs.
    """
    if not correctness:
        return 0.0, 0.0
    rng = random.Random(_BOOTSTRAP_SEED)
    n = len(correctness)
    samples: list[float] = []
    for _ in range(n_resamples):
        s = sum(rng.choice(correctness) for _ in range(n))
        samples.append(s / n * 100.0)
    samples.sort()
    lo_idx = max(0, int(0.025 * n_resamples) - 1)
    hi_idx = min(n_resamples - 1, int(0.975 * n_resamples))
    return samples[lo_idx], samples[hi_idx]


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
    # was re-run after DAG planner bug fixes; earlier eval runs appended 3 extra tasks
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
            "replans",
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
        # Bootstrap CI for accuracy — pool task-level outcomes across seeds.
        pooled: list[int] = []
        for s in seeds:
            pooled.extend(per_seed[s].get("_correctness_vector", []))
        ci_lo, ci_hi = _bootstrap_ci_pct(pooled)
        cell_summary["accuracy_pct"]["ci_lo"] = ci_lo
        cell_summary["accuracy_pct"]["ci_hi"] = ci_hi
        cell_summary["accuracy_pct"]["n_pooled"] = len(pooled)
        result[cell] = cell_summary
    return result


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def _fmt_pct(mean: float, std: Optional[float]) -> str:
    if std is None:
        return f"{mean:.1f}% ± —"
    return f"{mean:.1f}% ± {std:.1f}pp"


def _fmt_pct_with_ci(metric_dict: dict[str, Any]) -> str:
    """Accuracy display including stddev-across-seeds AND 95% bootstrap CI."""
    mean = metric_dict["mean"]
    std = metric_dict.get("std")
    ci_lo = metric_dict.get("ci_lo")
    ci_hi = metric_dict.get("ci_hi")
    stddev_str = f"± {std:.1f}pp" if std is not None else "± —"
    if ci_lo is None or ci_hi is None:
        return f"{mean:.1f}% {stddev_str}"
    return f"{mean:.1f}% {stddev_str} [95% CI: {ci_lo:.1f}%–{ci_hi:.1f}%]"


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
    "bfcl_parallel": "BFCL v4 parallel (function-call accuracy, AST judge)",
}
BENCHMARK_SHORT = {
    "hotpotqa": "HotpotQA bridge",
    "hotpotqa_comparison": "HotpotQA comparison",
    "github": "GitHub",
    "bfcl_parallel": "BFCL parallel",
}
BENCHMARK_ORDER = ["hotpotqa", "hotpotqa_comparison", "github", "bfcl_parallel"]


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
    strategies_present = [s for s in STRATEGY_ORDER if any((bm, s) in agg for bm in benchmarks_present)]

    # ---- Accuracy summary matrix (rows = strategies, cols = benchmarks) ----
    lines.append(f"## Accuracy summary ({len(strategies_present)} strategies × {len(benchmarks_present)} benchmarks)")
    lines.append("")
    lines.append(
        "Each cell shows `mean ± stddev-across-seeds [95% bootstrap CI]`. "
        "Bootstrap CI is computed by resampling the pooled per-task "
        "correctness vector across all seeds (with replacement, "
        f"{_BOOTSTRAP_N} resamples)."
    )
    lines.append("")
    bm_headers = [BENCHMARK_SHORT.get(bm, bm) for bm in benchmarks_present]
    lines.append("| Strategy | " + " | ".join(bm_headers) + " |")
    lines.append("| --- | " + " | ".join(["---"] * len(benchmarks_present)) + " |")
    for st in strategies_present:
        cells = []
        for bm in benchmarks_present:
            if (bm, st) in agg:
                cells.append(_fmt_pct_with_ci(agg[(bm, st)]["accuracy_pct"]))
            else:
                cells.append("—")
        lines.append(f"| {STRATEGY_DISPLAY[st]} | " + " | ".join(cells) + " |")
    lines.append("")

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

        def accuracy_row() -> None:
            cells = []
            for s in STRATEGY_ORDER:
                if (bm, s) not in agg:
                    continue
                cells.append(_fmt_pct_with_ci(agg[(bm, s)]["accuracy_pct"]))
            lines.append("| Accuracy | " + " | ".join(cells) + " |")

        accuracy_row()
        row("LLM calls / task", _fmt_num, "llm_calls")
        row("Tools executed / task", _fmt_num, "tools_executed")
        row("Replans / task", _fmt_num, "replans")
        row("Cost / task", _fmt_cost, "cost_usd")
        row("Wall-clock p50", _fmt_secs, "p50_latency_s")
        row("Wall-clock mean", _fmt_secs, "wall_clock_mean_s")
        row("Errors (total)", lambda m, s: _fmt_num(m, s, digits=1), "errors")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DAG-with-replan ablation table
# ---------------------------------------------------------------------------
ABLATION_BENCHMARK: str = "hotpotqa"
ABLATION_BASELINE: str = "dag_planner"
ABLATION_ORDER: list[tuple[str, str]] = [
    ("dag_planner", "Base DAG planner"),
    ("dag_replan_cap2", "+ any_failure trigger (cap=2)"),
    ("dag_replan_cap2_empty", "+ empty_synth trigger (cap=2)"),
    ("dag_replan_cap5_empty_top3", "+ empty_synth + top-3 (cap=5)"),
    ("dag_replan_aggressive", "+ diversification + replan-context + CoT (cap=5)"),
    ("dag_replan_max", "++ any_or_empty + cap=8 + top-5 (most aggressive)"),
]

# Leave-one-out ablations of `dag_replan_aggressive`. Each row removes ONE
# component from the aggressive variant.
LEAVE_ONE_OUT_ORDER: list[tuple[str, str]] = [
    ("dag_replan_aggressive", "aggressive (all 5 modifications)"),
    ("dag_replan_aggressive_no_diversify", "− diversification"),
    ("dag_replan_aggressive_no_cot", "− CoT synth"),
    ("dag_replan_aggressive_no_topk", "− top-K fan-out (back to top-1)"),
    ("dag_replan_aggressive_no_emptysynth", "− empty_synth trigger (back to any_failure)"),
]


def _replan_ablation_table(
    agg: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> str:
    """DAG-with-replan ablation table on the bridge benchmark (the cell
    where replanning is supposed to help)."""
    lines: list[str] = []
    lines.append(
        f"## DAG-with-replan ablation ({BENCHMARK_SHORT.get(ABLATION_BENCHMARK, ABLATION_BENCHMARK)})"
    )
    lines.append("")
    lines.append(
        "Cumulative contribution of each modification. Each row reports "
        "accuracy ± stddev across seeds, with a delta vs the **base DAG "
        "planner** row."
    )
    lines.append("")

    base_cell = agg.get((ABLATION_BENCHMARK, ABLATION_BASELINE))
    base_mean = base_cell["accuracy_pct"]["mean"] if base_cell else None

    lines.append("| Variant | Accuracy | Δ vs base | LLM calls / task | Replans / task |")
    lines.append("| --- | --- | --- | --- | --- |")

    for strategy_id, label in ABLATION_ORDER:
        cell = agg.get((ABLATION_BENCHMARK, strategy_id))
        if cell is None:
            lines.append(f"| {label} | _(no data)_ | — | — | — |")
            continue
        acc_m = cell["accuracy_pct"]["mean"]
        acc_s = cell["accuracy_pct"]["std"]
        acc_cell = _fmt_pct(acc_m, acc_s)
        if base_mean is None or strategy_id == ABLATION_BASELINE:
            delta = "—"
        else:
            d = acc_m - base_mean
            sign = "+" if d >= 0 else ""
            delta = f"{sign}{d:.1f}pp"
        llm_m = cell["llm_calls"]["mean"]
        llm_s = cell["llm_calls"]["std"]
        llm_cell = _fmt_num(llm_m, llm_s)
        rep_m = cell["replans"]["mean"]
        rep_s = cell["replans"]["std"]
        rep_cell = _fmt_num(rep_m, rep_s)
        lines.append(
            f"| {label} | {acc_cell} | {delta} | {llm_cell} | {rep_cell} |"
        )
    lines.append("")

    # ---- Leave-one-out table -----------------------------------------------
    lines.append(
        f"### Leave-one-out ablation ({BENCHMARK_SHORT.get(ABLATION_BENCHMARK, ABLATION_BENCHMARK)})"
    )
    lines.append("")
    lines.append(
        "Each row removes one component from the aggressive variant. "
        "Δ vs aggressive shows the impact of REMOVING that component — "
        "if Δ is negative (i.e. accuracy drops), the component was "
        "helping; if Δ is positive, the component was hurting."
    )
    lines.append("")
    aggr_cell = agg.get((ABLATION_BENCHMARK, "dag_replan_aggressive"))
    aggr_mean = aggr_cell["accuracy_pct"]["mean"] if aggr_cell else None
    lines.append("| Variant | Accuracy | Δ vs aggressive | LLM calls / task | Replans / task |")
    lines.append("| --- | --- | --- | --- | --- |")
    for strategy_id, label in LEAVE_ONE_OUT_ORDER:
        cell = agg.get((ABLATION_BENCHMARK, strategy_id))
        if cell is None:
            lines.append(f"| {label} | _(no data)_ | — | — | — |")
            continue
        acc_m = cell["accuracy_pct"]["mean"]
        acc_s = cell["accuracy_pct"]["std"]
        acc_cell = _fmt_pct(acc_m, acc_s)
        if aggr_mean is None or strategy_id == "dag_replan_aggressive":
            delta = "—"
        else:
            d = acc_m - aggr_mean
            sign = "+" if d >= 0 else ""
            delta = f"{sign}{d:.1f}pp"
        llm_m = cell["llm_calls"]["mean"]
        llm_s = cell["llm_calls"]["std"]
        llm_cell = _fmt_num(llm_m, llm_s)
        rep_m = cell["replans"]["mean"]
        rep_s = cell["replans"]["std"]
        rep_cell = _fmt_num(rep_m, rep_s)
        lines.append(
            f"| {label} | {acc_cell} | {delta} | {llm_cell} | {rep_cell} |"
        )
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
    md = (
        render_markdown(agg)
        + "\n"
        + _replan_ablation_table(agg)
        + "\n"
        + _meaningful_pairs(agg)
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(md)

    print(md)
    print(f"\nSaved to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
