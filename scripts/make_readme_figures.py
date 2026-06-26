from __future__ import annotations

"""Generate the three README charts from ``results/results.json``.

  1. docs/figures/accuracy_matrix.png   — 5 strategies × 4 benchmarks grouped bars
  2. docs/figures/ablation_bridge.png   — cumulative ablation steps on bridge
  3. docs/figures/failure_modes.png     — stacked horizontal bars per strategy

Run:

    python scripts/make_readme_figures.py
"""

import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "results" / "results.json"
FIG_DIR = REPO_ROOT / "docs" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.linestyle": ":",
    "grid.alpha": 0.4,
    "axes.axisbelow": True,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})

# Muted, color-blind-friendly palette.
PALETTE = {
    "react":            "#4C72B0",
    "native_parallel":  "#55A868",
    "dag_planner":      "#C44E52",
    "dag_replan_top3":  "#8172B2",
    "dag_replan_max":   "#CCB974",
}


def _load_deduped() -> list[dict]:
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        rows = json.load(f)
    latest = {}
    for r in rows:
        k = (r["strategy"], r["benchmark"], r.get("seed"), r["task_id"])
        latest[k] = r
    return list(latest.values())


def _per_seed_accuracy(rows: list[dict], strategy: str, benchmark: str) -> list[float]:
    buckets: dict[int, list[bool]] = defaultdict(list)
    for r in rows:
        if r["strategy"] != strategy or r["benchmark"] != benchmark:
            continue
        buckets[r.get("seed")].append(bool(r.get("judge_correct")))
    return [sum(b) / len(b) * 100.0 for _, b in sorted(buckets.items()) if b]


def _mean_sd(accs: list[float]) -> tuple[float, float]:
    if not accs:
        return float("nan"), 0.0
    m = statistics.mean(accs)
    sd = statistics.stdev(accs) if len(accs) > 1 else 0.0
    return m, sd


# -----------------------------------------------------------------------------
# Figure 1 — accuracy matrix
# -----------------------------------------------------------------------------
def make_accuracy_matrix(rows: list[dict]) -> None:
    strategies = [
        ("react", "ReAct"),
        ("native_parallel", "Native parallel"),
        ("dag_planner", "DAG planner"),
        ("dag_replan_cap5_empty_top3", "DAG replan ×5\n(empty_synth, top-3)"),
        ("dag_replan_max", "DAG replan max\n(cap=8, top-5,\nany_or_empty)"),
    ]
    benchmarks = [
        ("hotpotqa",            "HotpotQA bridge"),
        ("hotpotqa_comparison", "HotpotQA comparison"),
        ("github",              "GitHub"),
        ("bfcl_parallel",       "BFCL parallel"),
    ]
    colors = [
        PALETTE["react"],
        PALETTE["native_parallel"],
        PALETTE["dag_planner"],
        PALETTE["dag_replan_top3"],
        PALETTE["dag_replan_max"],
    ]

    n_strats = len(strategies)
    n_bench = len(benchmarks)
    x = np.arange(n_bench)
    width = 0.16

    fig, ax = plt.subplots(figsize=(11, 5.4))
    for i, ((sid, slabel), color) in enumerate(zip(strategies, colors)):
        means = []
        sds = []
        for bid, _ in benchmarks:
            accs = _per_seed_accuracy(rows, sid, bid)
            m, sd = _mean_sd(accs)
            means.append(m)
            sds.append(sd)
        offset = (i - (n_strats - 1) / 2) * width
        bars = ax.bar(
            x + offset, means, width,
            yerr=sds, capsize=3,
            label=slabel,
            color=color, edgecolor="white", linewidth=0.6,
            error_kw={"elinewidth": 0.9, "ecolor": "#444"},
        )
        # value labels above each bar
        for rect, m in zip(bars, means):
            if not np.isnan(m):
                ax.annotate(
                    f"{m:.0f}",
                    xy=(rect.get_x() + rect.get_width() / 2, m),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=8.5, color="#222",
                )

    ax.set_xticks(x)
    ax.set_xticklabels([b[1] for b in benchmarks])
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 110)
    ax.set_yticks(range(0, 101, 20))
    ax.set_title(
        "Accuracy across 5 strategies × 4 benchmarks  —  mean ± stddev across 3 seeds",
        pad=14,
    )
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.10),
        ncol=5, frameon=False, fontsize=9.5,
    )
    fig.savefig(FIG_DIR / "accuracy_matrix.png")
    plt.close(fig)
    print("Wrote", FIG_DIR / "accuracy_matrix.png")


# -----------------------------------------------------------------------------
# Figure 2 — ablation on bridge
# -----------------------------------------------------------------------------
def make_ablation_bridge(rows: list[dict]) -> None:
    # Cumulative build-up.
    steps = [
        ("dag_planner",                          "Base DAG\nplanner"),
        ("dag_replan_cap2",                      "+ any_failure\n(cap=2)"),
        ("dag_replan_cap2_empty",                "+ empty_synth\n(cap=2)"),
        ("dag_replan_cap5_empty_top3",           "+ top-3\n(cap=5)"),
        ("dag_replan_aggressive_no_cot",         "+ diversify\n+ replan-ctx\n(no CoT, n=5)"),
        ("dag_replan_max",                       "+ any_or_empty\n+ cap=8 + top-5\n(max)"),
    ]
    means, sds = [], []
    for sid, _ in steps:
        accs = _per_seed_accuracy(rows, sid, "hotpotqa")
        m, sd = _mean_sd(accs)
        means.append(m); sds.append(sd)
    base = means[0]
    deltas = [m - base for m in means]

    fig, ax = plt.subplots(figsize=(11, 5.4))
    x = np.arange(len(steps))
    # Gradient from red (base) → green (most aggressive)
    cmap_colors = plt.cm.RdYlGn(np.linspace(0.15, 0.78, len(steps)))
    bars = ax.bar(
        x, means, yerr=sds, capsize=4,
        color=cmap_colors, edgecolor="white", linewidth=0.7,
        error_kw={"elinewidth": 1.0, "ecolor": "#333"},
        width=0.7,
    )
    # Annotate each bar with mean and Δ vs base.
    for i, (rect, m, d) in enumerate(zip(bars, means, deltas)):
        ax.annotate(
            f"{m:.1f}%",
            xy=(rect.get_x() + rect.get_width() / 2, m),
            xytext=(0, 4), textcoords="offset points",
            ha="center", va="bottom", fontsize=10, fontweight="bold", color="#111",
        )
        if i > 0:
            ax.annotate(
                f"Δ +{d:.1f}pp",
                xy=(rect.get_x() + rect.get_width() / 2, m),
                xytext=(0, 20), textcoords="offset points",
                ha="center", va="bottom", fontsize=8.5, color="#444",
            )
    # Highlight the largest jump (empty_synth) and the headline-aggressive bar.
    ax.annotate(
        "empty_synth trigger:\nstrongest single jump (+16.7pp)",
        xy=(2, means[2]), xytext=(2, 70),
        ha="center", fontsize=9, color="#0a4d22",
        arrowprops=dict(arrowstyle="->", color="#0a4d22", lw=1),
    )
    ax.annotate(
        f"DAG replan max:\n{means[-1]:.1f}% (Δ +{deltas[-1]:.1f}pp,\n81% of ReAct gap closed)",
        xy=(len(steps) - 1, means[-1]), xytext=(len(steps) - 1.4, 78),
        ha="center", fontsize=9, color="#08401b",
        arrowprops=dict(arrowstyle="->", color="#08401b", lw=1),
    )

    ax.set_xticks(x)
    ax.set_xticklabels([lbl for _, lbl in steps], fontsize=9.5)
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 90)
    ax.set_title(
        "Cumulative DAG-with-replan ablation on HotpotQA bridge\n"
        "(mean ± stddev; seeds=7/17/42; n=30 tasks/seed)",
        pad=14,
    )
    fig.savefig(FIG_DIR / "ablation_bridge.png")
    plt.close(fig)
    print("Wrote", FIG_DIR / "ablation_bridge.png")


# -----------------------------------------------------------------------------
# Figure 3 — failure-mode composition (stacked horizontal bars)
# -----------------------------------------------------------------------------
def make_failure_modes() -> None:
    """Re-derive failure-mode breakdown from results.json by importing the
    classifier in :mod:`scripts.analyze_failures`. The script writes a
    markdown table; we parse it back for visualization."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "analyze_failures",
        REPO_ROOT / "scripts" / "analyze_failures.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    rows = _load_deduped()
    # Use the classifier directly.
    classify = getattr(mod, "classify_record", None) or getattr(mod, "_classify", None)
    # Fall back to reparsing the .md if no module-level function exists.
    if classify is None:
        md_path = REPO_ROOT / "results" / "failure_modes.md"
        with open(md_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Parse table rows.
        data = {}
        for line in lines:
            if not line.startswith("| "): continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not cells or cells[0] in ("Strategy", "---"):
                continue
            try:
                strat = cells[0]
                # PCT cells are like "7.5% (8)" or "—"
                vals = []
                for c in cells[1:6]:  # PVE, JD, HDE, HR, WFR
                    if c == "—":
                        vals.append(0)
                    else:
                        # take the count from "(n)"
                        n = c.split("(")[1].rstrip(")")
                        vals.append(int(n))
                # OTHER
                c = cells[6]
                vals.append(0 if c == "—" else int(c.split("(")[1].rstrip(")")))
                total = int(cells[7])
                data[strat] = (vals, total)
            except (IndexError, ValueError):
                continue
    else:
        # Build buckets in-place
        cats = ["PLAN_VALIDATION_ERROR", "JUDGE_DISPUTED", "HEDGED_DESPITE_EVIDENCE",
                "HEDGED_REFUSAL", "WRONG_FIRST_RETRIEVAL", "OTHER"]
        data = {}
        for r in rows:
            if r.get("judge_correct"):
                continue
            bucket = classify(r)
            strat = r["strategy"]
            if strat not in data:
                data[strat] = ([0] * len(cats), 0)
            vals, total = data[strat]
            try:
                idx = cats.index(bucket)
            except ValueError:
                idx = cats.index("OTHER")
            vals[idx] += 1
            data[strat] = (vals, total + 1)

    # Only the 5 headline strategies, in the same order as accuracy_matrix.
    show_order = [
        ("react",                       "ReAct"),
        ("native_parallel",             "Native parallel"),
        ("dag_planner",                 "DAG planner"),
        ("dag_replan_cap5_empty_top3",  "DAG replan ×5 (top-3)"),
        ("dag_replan_max",              "DAG replan max"),
    ]
    cat_labels = [
        "PLAN_VALIDATION", "JUDGE_DISPUTED",
        "HEDGED_REFUSAL", "WRONG_FIRST_RETRIEVAL", "OTHER",
    ]
    # collapse HEDGED_DESPITE_EVIDENCE (always empty) into HEDGED_REFUSAL.
    # Map analyze_failures column order [PVE, JD, HDE, HR, WFR, OTHER] → display.
    cat_palette = ["#8e7cc3", "#90a4ae", "#ef9a9a", "#ffb74d", "#bdbdbd"]

    fig, ax = plt.subplots(figsize=(11, 4.4))
    strat_labels = [lbl for _, lbl in show_order]
    y = np.arange(len(show_order))

    # Precompute proportion stacks.
    all_props = []
    totals = []
    for sid, _ in show_order:
        vals, total = data.get(sid, ([0] * 6, 0))
        if total == 0:
            all_props.append([0] * 5)
            totals.append(0)
            continue
        # Collapse HDE (idx 2) into HR (idx 3) for display.
        collapsed = [vals[0], vals[1], vals[3] + vals[2], vals[4], vals[5]]
        all_props.append([v / total * 100.0 for v in collapsed])
        totals.append(total)

    left = np.zeros(len(show_order))
    for ci, (lbl, color) in enumerate(zip(cat_labels, cat_palette)):
        widths = np.array([p[ci] for p in all_props])
        ax.barh(y, widths, left=left, label=lbl, color=color, edgecolor="white", linewidth=0.6)
        # annotate the largest two segments per strategy with %
        for yi, w in zip(y, widths):
            if w >= 10:
                ax.text(left[yi] + w / 2, yi, f"{w:.0f}%",
                        ha="center", va="center", fontsize=8.5, color="#222")
        left += widths

    ax.set_yticks(y)
    ax.set_yticklabels(strat_labels)
    ax.invert_yaxis()
    ax.set_xlabel("Share of strategy's failures (%)")
    ax.set_xlim(0, 100)
    # Annotate total failure count on the right of each bar.
    for yi, t in zip(y, totals):
        ax.text(101, yi, f"  n={t}", va="center", fontsize=9, color="#555")
    ax.set_title(
        "Failure-mode composition (deduped, all benchmarks × seeds)",
        pad=12,
    )
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.12),
        ncol=5, frameon=False, fontsize=9,
    )
    fig.savefig(FIG_DIR / "failure_modes.png")
    plt.close(fig)
    print("Wrote", FIG_DIR / "failure_modes.png")


def main() -> int:
    rows = _load_deduped()
    make_accuracy_matrix(rows)
    make_ablation_bridge(rows)
    make_failure_modes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
