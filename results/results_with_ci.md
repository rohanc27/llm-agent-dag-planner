# Multi-seed eval — mean ± stddev across seeds

Each cell aggregates per-seed scalars (one accuracy / mean-LLM-calls etc. per seed) across seeds. Stddev is the sample stddev of those per-seed values — not the within-seed variance. `±—` means only one seed is present.

## Accuracy summary (15 strategies × 4 benchmarks)

Each cell shows `mean ± stddev-across-seeds [95% bootstrap CI]`. Bootstrap CI is computed by resampling the pooled per-task correctness vector across all seeds (with replacement, 1000 resamples).

| Strategy | HotpotQA bridge | HotpotQA comparison | GitHub | BFCL parallel |
| --- | --- | --- | --- | --- |
| ReAct | 57.8% ± 7.7pp [95% CI: 47.8%–67.8%] | 86.7% ± 5.8pp [95% CI: 80.0%–93.3%] | 98.7% ± 2.3pp [95% CI: 96.0%–100.0%] | 82.2% ± 1.9pp [95% CI: 73.3%–90.0%] |
| Native parallel | 61.1% ± 11.7pp [95% CI: 51.1%–71.1%] | 84.4% ± 8.4pp [95% CI: 76.7%–91.1%] | 100.0% ± 0.0pp [95% CI: 100.0%–100.0%] | 83.3% ± 0.0pp [95% CI: 74.4%–91.1%] |
| DAG planner | 28.9% ± 13.5pp [95% CI: 20.0%–37.8%] | 81.1% ± 1.9pp [95% CI: 73.3%–88.9%] | 96.0% ± 4.0pp [95% CI: 90.7%–100.0%] | 75.6% ± 5.1pp [95% CI: 66.7%–84.4%] |
| DAG replan ×2 (any_failure) | 37.8% ± 12.6pp [95% CI: 27.8%–47.8%] | 80.0% ± 3.3pp [95% CI: 72.2%–87.8%] | 98.7% ± 2.3pp [95% CI: 96.0%–100.0%] | — |
| DAG replan ×5 (any_failure) | 37.8% ± 12.6pp [95% CI: 27.8%–47.8%] | 75.6% ± 6.9pp [95% CI: 66.7%–83.3%] | 90.7% ± 6.1pp [95% CI: 82.7%–97.3%] | — |
| DAG replan ×2 (empty_synth) | 45.6% ± 5.1pp [95% CI: 35.6%–55.6%] | 82.2% ± 1.9pp [95% CI: 74.4%–90.0%] | 97.3% ± 2.3pp [95% CI: 93.3%–100.0%] | — |
| DAG replan ×5 (empty_synth) | 46.7% ± 6.7pp [95% CI: 36.7%–57.8%] | 77.8% ± 3.8pp [95% CI: 68.9%–86.7%] | 96.0% ± 0.0pp [95% CI: 90.7%–100.0%] | — |
| DAG replan ×2 (empty_synth, top-3) | 43.3% ± 14.5pp [95% CI: 33.3%–54.4%] | 88.9% ± 1.9pp [95% CI: 82.2%–94.4%] | 97.3% ± 4.6pp [95% CI: 93.3%–100.0%] | — |
| DAG replan ×5 (empty_synth, top-3) | 48.9% ± 1.9pp [95% CI: 38.9%–60.0%] | 83.3% ± 0.0pp [95% CI: 75.6%–91.1%] | 90.7% ± 6.1pp [95% CI: 84.0%–97.3%] | 75.6% ± 1.9pp [95% CI: 65.6%–84.4%] |
| DAG replan aggressive (cap=5, diversif+CoT) | 44.4% ± 21.4pp [95% CI: 33.3%–55.6%] | 85.6% ± 3.8pp [95% CI: 77.8%–92.2%] | 94.7% ± 2.3pp [95% CI: 89.3%–98.7%] | — |
| DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) | 52.2% ± 13.5pp [95% CI: 42.2%–62.2%] | 85.6% ± 3.8pp [95% CI: 77.8%–92.2%] | 97.3% ± 2.3pp [95% CI: 93.3%–100.0%] | — |
| aggressive − diversification | 50.0% ± 5.8pp [95% CI: 38.9%–60.0%] | — | — | — |
| aggressive − CoT | 48.7% ± 8.0pp [95% CI: 40.0%–56.7%] | 83.3% ± 6.2pp [95% CI: 77.3%–88.7%] | 94.4% ± 3.6pp [95% CI: 90.4%–98.4%] | 75.6% ± 1.9pp [95% CI: 66.7%–85.6%] |
| aggressive − top-K (back to top-1) | 42.2% ± 8.4pp [95% CI: 32.2%–52.2%] | — | — | — |
| aggressive − empty_synth (back to any_failure) | 41.1% ± 10.7pp [95% CI: 31.1%–51.1%] | — | — | — |

## HotpotQA (bridge — adaptive 2-hop)

_Seeds: [7, 17, 42]; n per seed: 30._

| Metric | ReAct | Native parallel | DAG planner | DAG replan ×2 (any_failure) | DAG replan ×5 (any_failure) | DAG replan ×2 (empty_synth) | DAG replan ×5 (empty_synth) | DAG replan ×2 (empty_synth, top-3) | DAG replan ×5 (empty_synth, top-3) | DAG replan aggressive (cap=5, diversif+CoT) | DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) | aggressive − diversification | aggressive − CoT | aggressive − top-K (back to top-1) | aggressive − empty_synth (back to any_failure) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Accuracy | 57.8% ± 7.7pp [95% CI: 47.8%–67.8%] | 61.1% ± 11.7pp [95% CI: 51.1%–71.1%] | 28.9% ± 13.5pp [95% CI: 20.0%–37.8%] | 37.8% ± 12.6pp [95% CI: 27.8%–47.8%] | 37.8% ± 12.6pp [95% CI: 27.8%–47.8%] | 45.6% ± 5.1pp [95% CI: 35.6%–55.6%] | 46.7% ± 6.7pp [95% CI: 36.7%–57.8%] | 43.3% ± 14.5pp [95% CI: 33.3%–54.4%] | 48.9% ± 1.9pp [95% CI: 38.9%–60.0%] | 44.4% ± 21.4pp [95% CI: 33.3%–55.6%] | 52.2% ± 13.5pp [95% CI: 42.2%–62.2%] | 50.0% ± 5.8pp [95% CI: 38.9%–60.0%] | 48.7% ± 8.0pp [95% CI: 40.0%–56.7%] | 42.2% ± 8.4pp [95% CI: 32.2%–52.2%] | 41.1% ± 10.7pp [95% CI: 31.1%–51.1%] |
| LLM calls / task | 4.79 ± 0.18 | 4.93 ± 0.04 | 1.91 ± 0.02 | 2.02 ± 0.10 | 2.01 ± 0.05 | 2.76 ± 0.25 | 3.22 ± 0.11 | 2.64 ± 0.12 | 2.82 ± 0.36 | 3.14 ± 0.79 | 2.96 ± 0.29 | 3.06 ± 0.69 | 3.02 ± 0.36 | 2.95 ± 0.55 | 2.09 ± 0.08 |
| Tools executed / task | 3.82 ± 0.20 | 3.97 ± 0.06 | 2.66 ± 0.26 | 2.89 ± 0.36 | 2.88 ± 0.39 | 3.76 ± 0.31 | 4.72 ± 0.16 | 6.23 ± 0.30 | 6.19 ± 0.66 | 7.23 ± 1.58 | 9.40 ± 0.86 | 7.31 ± 2.07 | 6.02 ± 0.60 | 4.02 ± 0.78 | 5.01 ± 0.65 |
| Replans / task | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.10 ± 0.09 | 0.07 ± 0.03 | 0.43 ± 0.12 | 0.67 ± 0.08 | 0.37 ± 0.03 | 0.44 ± 0.20 | 0.59 ± 0.40 | 0.56 ± 0.15 | 0.55 ± 0.33 | 0.55 ± 0.19 | 0.55 ± 0.24 | 0.14 ± 0.10 |
| Cost / task | $0.0015 ± $0.0002 | $0.0015 ± $0.0000 | $0.0010 ± $0.0000 | $0.0011 ± $0.0001 | $0.0010 ± $0.0001 | $0.0014 ± $0.0001 | $0.0018 ± $0.0001 | $0.0021 ± $0.0000 | $0.0021 ± $0.0003 | $0.0027 ± $0.0007 | $0.0032 ± $0.0004 | $0.0027 ± $0.0008 | $0.0022 ± $0.0002 | $0.0019 ± $0.0003 | $0.0018 ± $0.0002 |
| Wall-clock p50 | 5.70s ± 0.43s | 8.10s ± 1.01s | 6.46s ± 0.78s | 5.71s ± 0.25s | 6.67s ± 0.88s | 6.39s ± 1.86s | 8.72s ± 0.77s | 8.63s ± 0.41s | 8.84s ± 1.37s | 11.10s ± 2.30s | 13.99s ± 3.59s | 11.63s ± 1.52s | 9.37s ± 1.80s | 7.10s ± 0.48s | 9.38s ± 1.32s |
| Wall-clock mean | 7.70s ± 0.95s | 9.73s ± 0.55s | 7.86s ± 0.40s | 8.29s ± 1.63s | 9.05s ± 0.83s | 11.17s ± 1.73s | 15.49s ± 2.00s | 12.12s ± 1.75s | 13.51s ± 1.75s | 15.90s ± 4.25s | 20.00s ± 2.80s | 16.01s ± 3.85s | 15.04s ± 1.93s | 14.86s ± 1.16s | 11.41s ± 0.42s |
| Errors (total) | 1.0 ± 1.7 | 0.3 ± 0.6 | 1.0 ± 1.0 | 0.3 ± 0.6 | 0.0 ± 0.0 | 0.3 ± 0.6 | 0.3 ± 0.6 | 0.0 ± 0.0 | 0.0 ± 0.0 | 2.0 ± 1.0 | 0.0 ± 0.0 | 0.3 ± 0.6 | 0.0 ± 0.0 | 0.3 ± 0.6 | 0.0 ± 0.0 |

## HotpotQA (comparison — inherently parallel)

_Seeds: [7, 17, 42]; n per seed: 30._

| Metric | ReAct | Native parallel | DAG planner | DAG replan ×2 (any_failure) | DAG replan ×5 (any_failure) | DAG replan ×2 (empty_synth) | DAG replan ×5 (empty_synth) | DAG replan ×2 (empty_synth, top-3) | DAG replan ×5 (empty_synth, top-3) | DAG replan aggressive (cap=5, diversif+CoT) | DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) | aggressive − CoT |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Accuracy | 86.7% ± 5.8pp [95% CI: 80.0%–93.3%] | 84.4% ± 8.4pp [95% CI: 76.7%–91.1%] | 81.1% ± 1.9pp [95% CI: 73.3%–88.9%] | 80.0% ± 3.3pp [95% CI: 72.2%–87.8%] | 75.6% ± 6.9pp [95% CI: 66.7%–83.3%] | 82.2% ± 1.9pp [95% CI: 74.4%–90.0%] | 77.8% ± 3.8pp [95% CI: 68.9%–86.7%] | 88.9% ± 1.9pp [95% CI: 82.2%–94.4%] | 83.3% ± 0.0pp [95% CI: 75.6%–91.1%] | 85.6% ± 3.8pp [95% CI: 77.8%–92.2%] | 85.6% ± 3.8pp [95% CI: 77.8%–92.2%] | 83.3% ± 6.2pp [95% CI: 77.3%–88.7%] |
| LLM calls / task | 4.97 ± 0.09 | 4.38 ± 0.06 | 2.00 ± 0.00 | 2.01 ± 0.02 | 2.00 ± 0.00 | 2.25 ± 0.08 | 2.20 ± 0.23 | 2.27 ± 0.20 | 2.27 ± 0.13 | 2.18 ± 0.09 | 2.07 ± 0.07 | 2.35 ± 0.18 |
| Tools executed / task | 3.98 ± 0.10 | 4.09 ± 0.13 | 3.82 ± 0.06 | 3.89 ± 0.08 | 3.86 ± 0.21 | 4.16 ± 0.04 | 4.12 ± 0.26 | 6.31 ± 0.84 | 5.77 ± 0.81 | 5.28 ± 0.69 | 6.90 ± 1.46 | 6.07 ± 0.48 |
| Replans / task | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.01 ± 0.02 | 0.00 ± 0.00 | 0.12 ± 0.04 | 0.10 ± 0.11 | 0.13 ± 0.10 | 0.13 ± 0.07 | 0.09 ± 0.04 | 0.04 ± 0.05 | 0.17 ± 0.09 |
| Cost / task | $0.0015 ± $0.0000 | $0.0013 ± $0.0001 | $0.0011 ± $0.0000 | $0.0012 ± $0.0000 | $0.0012 ± $0.0000 | $0.0013 ± $0.0000 | $0.0013 ± $0.0001 | $0.0018 ± $0.0003 | $0.0018 ± $0.0003 | $0.0018 ± $0.0002 | $0.0021 ± $0.0003 | $0.0018 ± $0.0001 |
| Wall-clock p50 | 5.49s ± 0.76s | 6.40s ± 0.48s | 4.58s ± 0.10s | 4.67s ± 0.21s | 4.95s ± 0.35s | 4.62s ± 0.07s | 4.99s ± 0.49s | 5.67s ± 0.37s | 5.35s ± 0.29s | 5.63s ± 0.13s | 8.19s ± 4.01s | 5.47s ± 0.42s |
| Wall-clock mean | 6.71s ± 0.66s | 6.97s ± 0.19s | 4.95s ± 0.46s | 5.26s ± 0.16s | 5.51s ± 0.37s | 6.16s ± 0.23s | 6.06s ± 0.79s | 7.11s ± 0.78s | 6.88s ± 1.05s | 6.49s ± 0.38s | 9.94s ± 5.54s | 7.99s ± 0.85s |
| Errors (total) | 0.7 ± 0.6 | 1.0 ± 1.7 | 0.3 ± 0.6 | 0.3 ± 0.6 | 0.0 ± 0.0 | 0.3 ± 0.6 | 1.3 ± 2.3 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.7 ± 1.2 | 0.0 ± 0.0 | 0.0 ± 0.0 |

## GitHub (structurally predictable multi-entity)

_Seeds: [7, 17, 42]; n per seed: 25._

| Metric | ReAct | Native parallel | DAG planner | DAG replan ×2 (any_failure) | DAG replan ×5 (any_failure) | DAG replan ×2 (empty_synth) | DAG replan ×5 (empty_synth) | DAG replan ×2 (empty_synth, top-3) | DAG replan ×5 (empty_synth, top-3) | DAG replan aggressive (cap=5, diversif+CoT) | DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) | aggressive − CoT |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Accuracy | 98.7% ± 2.3pp [95% CI: 96.0%–100.0%] | 100.0% ± 0.0pp [95% CI: 100.0%–100.0%] | 96.0% ± 4.0pp [95% CI: 90.7%–100.0%] | 98.7% ± 2.3pp [95% CI: 96.0%–100.0%] | 90.7% ± 6.1pp [95% CI: 82.7%–97.3%] | 97.3% ± 2.3pp [95% CI: 93.3%–100.0%] | 96.0% ± 0.0pp [95% CI: 90.7%–100.0%] | 97.3% ± 4.6pp [95% CI: 93.3%–100.0%] | 90.7% ± 6.1pp [95% CI: 84.0%–97.3%] | 94.7% ± 2.3pp [95% CI: 89.3%–98.7%] | 97.3% ± 2.3pp [95% CI: 93.3%–100.0%] | 94.4% ± 3.6pp [95% CI: 90.4%–98.4%] |
| LLM calls / task | 3.84 ± 0.00 | 2.40 ± 0.00 | 2.00 ± 0.00 | 2.00 ± 0.00 | 2.00 ± 0.00 | 2.00 ± 0.00 | 2.00 ± 0.00 | 2.00 ± 0.00 | 2.00 ± 0.00 | 2.00 ± 0.00 | 2.00 ± 0.00 | 2.00 ± 0.00 |
| Tools executed / task | 2.84 ± 0.00 | 2.84 ± 0.00 | 3.03 ± 0.02 | 2.97 ± 0.05 | 2.97 ± 0.07 | 3.01 ± 0.02 | 2.99 ± 0.06 | 3.04 ± 0.00 | 3.00 ± 0.04 | 3.00 ± 0.07 | 2.99 ± 0.06 | 3.03 ± 0.02 |
| Replans / task | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Cost / task | $0.0012 ± $0.0000 | $0.0008 ± $0.0000 | $0.0010 ± $0.0000 | $0.0010 ± $0.0000 | $0.0010 ± $0.0000 | $0.0010 ± $0.0000 | $0.0010 ± $0.0000 | $0.0011 ± $0.0000 | $0.0011 ± $0.0000 | $0.0013 ± $0.0000 | $0.0013 ± $0.0000 | $0.0011 ± $0.0000 |
| Wall-clock p50 | 4.37s ± 0.25s | 3.51s ± 0.17s | 4.19s ± 0.23s | 4.19s ± 0.23s | 4.36s ± 0.25s | 4.46s ± 0.21s | 4.33s ± 0.24s | 4.38s ± 0.12s | 4.35s ± 0.06s | 5.03s ± 0.10s | 5.47s ± 0.59s | 5.34s ± 1.12s |
| Wall-clock mean | 4.28s ± 0.14s | 3.76s ± 0.10s | 4.45s ± 0.09s | 4.75s ± 0.50s | 4.58s ± 0.10s | 4.57s ± 0.21s | 4.66s ± 0.16s | 4.60s ± 0.18s | 4.54s ± 0.12s | 5.14s ± 0.02s | 6.26s ± 1.52s | 6.45s ± 3.07s |
| Errors (total) | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1.3 ± 2.3 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1.0 ± 1.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |

## BFCL v4 parallel (function-call accuracy, AST judge)

_Seeds: [7, 17, 42]; n per seed: 30._

| Metric | ReAct | Native parallel | DAG planner | DAG replan ×5 (empty_synth, top-3) | aggressive − CoT |
| --- | --- | --- | --- | --- | --- |
| Accuracy | 82.2% ± 1.9pp [95% CI: 73.3%–90.0%] | 83.3% ± 0.0pp [95% CI: 74.4%–91.1%] | 75.6% ± 5.1pp [95% CI: 66.7%–84.4%] | 75.6% ± 1.9pp [95% CI: 65.6%–84.4%] | 75.6% ± 1.9pp [95% CI: 66.7%–85.6%] |
| LLM calls / task | 3.69 ± 0.06 | 2.20 ± 0.09 | 2.00 ± 0.00 | 3.28 ± 0.05 | 3.29 ± 0.51 |
| Tools executed / task | 2.69 ± 0.06 | 2.83 ± 0.12 | 2.70 ± 0.00 | 4.44 ± 0.24 | 4.27 ± 0.58 |
| Replans / task | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.64 ± 0.02 | 0.64 ± 0.25 |
| Cost / task | $0.0007 ± $0.0000 | $0.0006 ± $0.0000 | $0.0010 ± $0.0000 | $0.0018 ± $0.0001 | $0.0017 ± $0.0003 |
| Wall-clock p50 | 4.72s ± 0.19s | 3.36s ± 0.18s | 4.32s ± 0.22s | 5.73s ± 1.72s | 6.42s ± 1.91s |
| Wall-clock mean | 5.53s ± 0.73s | 3.84s ± 0.38s | 5.21s ± 0.40s | 10.99s ± 0.55s | 10.44s ± 2.45s |
| Errors (total) | 1.0 ± 0.0 | 1.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |

## DAG-with-replan ablation (HotpotQA bridge)

Cumulative contribution of each modification. Each row reports accuracy ± stddev across seeds, with a delta vs the **base DAG planner** row.

| Variant | Accuracy | Δ vs base | LLM calls / task | Replans / task |
| --- | --- | --- | --- | --- |
| Base DAG planner | 28.9% ± 13.5pp | — | 1.91 ± 0.02 | 0.00 ± 0.00 |
| + any_failure trigger (cap=2) | 37.8% ± 12.6pp | +8.9pp | 2.02 ± 0.10 | 0.10 ± 0.09 |
| + empty_synth trigger (cap=2) | 45.6% ± 5.1pp | +16.7pp | 2.76 ± 0.25 | 0.43 ± 0.12 |
| + empty_synth + top-3 (cap=5) | 48.9% ± 1.9pp | +20.0pp | 2.82 ± 0.36 | 0.44 ± 0.20 |
| + diversification + replan-context + CoT (cap=5) | 44.4% ± 21.4pp | +15.6pp | 3.14 ± 0.79 | 0.59 ± 0.40 |
| ++ any_or_empty + cap=8 + top-5 (most aggressive) | 52.2% ± 13.5pp | +23.3pp | 2.96 ± 0.29 | 0.56 ± 0.15 |

### Leave-one-out ablation (HotpotQA bridge)

Each row removes one component from the aggressive variant. Δ vs aggressive shows the impact of REMOVING that component — if Δ is negative (i.e. accuracy drops), the component was helping; if Δ is positive, the component was hurting.

| Variant | Accuracy | Δ vs aggressive | LLM calls / task | Replans / task |
| --- | --- | --- | --- | --- |
| aggressive (all 5 modifications) | 44.4% ± 21.4pp | — | 3.14 ± 0.79 | 0.59 ± 0.40 |
| − diversification | 50.0% ± 5.8pp | +5.6pp | 3.06 ± 0.69 | 0.55 ± 0.33 |
| − CoT synth | 48.7% ± 8.0pp | +4.2pp | 3.02 ± 0.36 | 0.55 ± 0.19 |
| − top-K fan-out (back to top-1) | 42.2% ± 8.4pp | -2.2pp | 2.95 ± 0.55 | 0.55 ± 0.24 |
| − empty_synth trigger (back to any_failure) | 41.1% ± 10.7pp | -3.3pp | 2.09 ± 0.08 | 0.14 ± 0.10 |

## Statistically meaningful differences

A pairwise gap is flagged **MEANINGFUL** when `|mean_a − mean_b| ≥ 2 × max(stddev_a, stddev_b)` — i.e. the two means are at least 2 stddevs apart on the wider of the two error bars. Cells with only one seed are skipped (no stddev defined).

### HotpotQA (bridge — adaptive 2-hop)

- **Accuracy**: ReAct (57.8pp) vs DAG planner (28.9pp) — gap 28.89pp, max σ 13.47pp → **MEANINGFUL** (2.1× max stddev)
- **Accuracy**: Native parallel (61.1pp) vs DAG planner (28.9pp) — gap 32.22pp, max σ 13.47pp → **MEANINGFUL** (2.4× max stddev)
- **LLM calls / task**: ReAct (4.79) vs DAG planner (1.91) — gap 2.89, max σ 0.18 → **MEANINGFUL** (15.7× max stddev)
- **LLM calls / task**: ReAct (4.79) vs DAG replan ×2 (any_failure) (2.02) — gap 2.77, max σ 0.18 → **MEANINGFUL** (15.0× max stddev)
- **LLM calls / task**: ReAct (4.79) vs DAG replan ×5 (any_failure) (2.01) — gap 2.78, max σ 0.18 → **MEANINGFUL** (15.1× max stddev)
- **LLM calls / task**: ReAct (4.79) vs DAG replan ×2 (empty_synth) (2.76) — gap 2.03, max σ 0.25 → **MEANINGFUL** (8.1× max stddev)
- **LLM calls / task**: ReAct (4.79) vs DAG replan ×5 (empty_synth) (3.22) — gap 1.57, max σ 0.18 → **MEANINGFUL** (8.5× max stddev)
- **LLM calls / task**: ReAct (4.79) vs DAG replan ×2 (empty_synth, top-3) (2.64) — gap 2.15, max σ 0.18 → **MEANINGFUL** (11.7× max stddev)
- **LLM calls / task**: ReAct (4.79) vs DAG replan ×5 (empty_synth, top-3) (2.82) — gap 1.97, max σ 0.36 → **MEANINGFUL** (5.5× max stddev)
- **LLM calls / task**: ReAct (4.79) vs DAG replan aggressive (cap=5, diversif+CoT) (3.14) — gap 1.66, max σ 0.79 → **MEANINGFUL** (2.1× max stddev)
- **LLM calls / task**: ReAct (4.79) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.96) — gap 1.84, max σ 0.29 → **MEANINGFUL** (6.4× max stddev)
- **LLM calls / task**: ReAct (4.79) vs aggressive − diversification (3.06) — gap 1.74, max σ 0.69 → **MEANINGFUL** (2.5× max stddev)
- **LLM calls / task**: ReAct (4.79) vs aggressive − CoT (3.02) — gap 1.77, max σ 0.36 → **MEANINGFUL** (4.9× max stddev)
- **LLM calls / task**: ReAct (4.79) vs aggressive − top-K (back to top-1) (2.95) — gap 1.84, max σ 0.55 → **MEANINGFUL** (3.3× max stddev)
- **LLM calls / task**: ReAct (4.79) vs aggressive − empty_synth (back to any_failure) (2.09) — gap 2.70, max σ 0.18 → **MEANINGFUL** (14.7× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs DAG planner (1.91) — gap 3.02, max σ 0.04 → **MEANINGFUL** (86.2× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs DAG replan ×2 (any_failure) (2.02) — gap 2.91, max σ 0.10 → **MEANINGFUL** (28.6× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs DAG replan ×5 (any_failure) (2.01) — gap 2.92, max σ 0.05 → **MEANINGFUL** (57.4× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs DAG replan ×2 (empty_synth) (2.76) — gap 2.17, max σ 0.25 → **MEANINGFUL** (8.6× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs DAG replan ×5 (empty_synth) (3.22) — gap 1.71, max σ 0.11 → **MEANINGFUL** (16.2× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs DAG replan ×2 (empty_synth, top-3) (2.64) — gap 2.29, max σ 0.12 → **MEANINGFUL** (19.5× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs DAG replan ×5 (empty_synth, top-3) (2.82) — gap 2.11, max σ 0.36 → **MEANINGFUL** (5.9× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs DAG replan aggressive (cap=5, diversif+CoT) (3.14) — gap 1.80, max σ 0.79 → **MEANINGFUL** (2.3× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.96) — gap 1.98, max σ 0.29 → **MEANINGFUL** (6.9× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs aggressive − diversification (3.06) — gap 1.88, max σ 0.69 → **MEANINGFUL** (2.7× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs aggressive − CoT (3.02) — gap 1.91, max σ 0.36 → **MEANINGFUL** (5.3× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs aggressive − top-K (back to top-1) (2.95) — gap 1.98, max σ 0.55 → **MEANINGFUL** (3.6× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs aggressive − empty_synth (back to any_failure) (2.09) — gap 2.84, max σ 0.08 → **MEANINGFUL** (36.9× max stddev)
- **LLM calls / task**: DAG planner (1.91) vs DAG replan ×5 (any_failure) (2.01) — gap 0.10, max σ 0.05 → **MEANINGFUL** (2.0× max stddev)
- **LLM calls / task**: DAG planner (1.91) vs DAG replan ×2 (empty_synth) (2.76) — gap 0.86, max σ 0.25 → **MEANINGFUL** (3.4× max stddev)
- **LLM calls / task**: DAG planner (1.91) vs DAG replan ×5 (empty_synth) (3.22) — gap 1.32, max σ 0.11 → **MEANINGFUL** (12.5× max stddev)
- **LLM calls / task**: DAG planner (1.91) vs DAG replan ×2 (empty_synth, top-3) (2.64) — gap 0.74, max σ 0.12 → **MEANINGFUL** (6.3× max stddev)
- **LLM calls / task**: DAG planner (1.91) vs DAG replan ×5 (empty_synth, top-3) (2.82) — gap 0.91, max σ 0.36 → **MEANINGFUL** (2.6× max stddev)
- **LLM calls / task**: DAG planner (1.91) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.96) — gap 1.05, max σ 0.29 → **MEANINGFUL** (3.6× max stddev)
- **LLM calls / task**: DAG planner (1.91) vs aggressive − CoT (3.02) — gap 1.11, max σ 0.36 → **MEANINGFUL** (3.1× max stddev)
- **LLM calls / task**: DAG planner (1.91) vs aggressive − empty_synth (back to any_failure) (2.09) — gap 0.18, max σ 0.08 → **MEANINGFUL** (2.4× max stddev)
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.02) vs DAG replan ×2 (empty_synth) (2.76) — gap 0.74, max σ 0.25 → **MEANINGFUL** (3.0× max stddev)
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.02) vs DAG replan ×5 (empty_synth) (3.22) — gap 1.20, max σ 0.11 → **MEANINGFUL** (11.4× max stddev)
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.02) vs DAG replan ×2 (empty_synth, top-3) (2.64) — gap 0.62, max σ 0.12 → **MEANINGFUL** (5.3× max stddev)
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.02) vs DAG replan ×5 (empty_synth, top-3) (2.82) — gap 0.80, max σ 0.36 → **MEANINGFUL** (2.2× max stddev)
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.02) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.96) — gap 0.93, max σ 0.29 → **MEANINGFUL** (3.2× max stddev)
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.02) vs aggressive − CoT (3.02) — gap 1.00, max σ 0.36 → **MEANINGFUL** (2.8× max stddev)
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.01) vs DAG replan ×2 (empty_synth) (2.76) — gap 0.75, max σ 0.25 → **MEANINGFUL** (3.0× max stddev)
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.01) vs DAG replan ×5 (empty_synth) (3.22) — gap 1.21, max σ 0.11 → **MEANINGFUL** (11.5× max stddev)
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.01) vs DAG replan ×2 (empty_synth, top-3) (2.64) — gap 0.63, max σ 0.12 → **MEANINGFUL** (5.4× max stddev)
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.01) vs DAG replan ×5 (empty_synth, top-3) (2.82) — gap 0.81, max σ 0.36 → **MEANINGFUL** (2.3× max stddev)
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.01) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.96) — gap 0.94, max σ 0.29 → **MEANINGFUL** (3.3× max stddev)
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.01) vs aggressive − CoT (3.02) — gap 1.01, max σ 0.36 → **MEANINGFUL** (2.8× max stddev)
- **LLM calls / task**: DAG replan ×2 (empty_synth) (2.76) vs aggressive − empty_synth (back to any_failure) (2.09) — gap 0.68, max σ 0.25 → **MEANINGFUL** (2.7× max stddev)
- **LLM calls / task**: DAG replan ×5 (empty_synth) (3.22) vs DAG replan ×2 (empty_synth, top-3) (2.64) — gap 0.58, max σ 0.12 → **MEANINGFUL** (4.9× max stddev)
- **LLM calls / task**: DAG replan ×5 (empty_synth) (3.22) vs aggressive − empty_synth (back to any_failure) (2.09) — gap 1.13, max σ 0.11 → **MEANINGFUL** (10.8× max stddev)
- **LLM calls / task**: DAG replan ×2 (empty_synth, top-3) (2.64) vs aggressive − empty_synth (back to any_failure) (2.09) — gap 0.56, max σ 0.12 → **MEANINGFUL** (4.7× max stddev)
- **LLM calls / task**: DAG replan ×5 (empty_synth, top-3) (2.82) vs aggressive − empty_synth (back to any_failure) (2.09) — gap 0.73, max σ 0.36 → **MEANINGFUL** (2.1× max stddev)
- **LLM calls / task**: DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.96) vs aggressive − empty_synth (back to any_failure) (2.09) — gap 0.87, max σ 0.29 → **MEANINGFUL** (3.0× max stddev)
- **LLM calls / task**: aggressive − CoT (3.02) vs aggressive − empty_synth (back to any_failure) (2.09) — gap 0.93, max σ 0.36 → **MEANINGFUL** (2.6× max stddev)
- **Tools executed / task**: ReAct (3.82) vs DAG planner (2.66) — gap 1.16, max σ 0.26 → **MEANINGFUL** (4.4× max stddev)
- **Tools executed / task**: ReAct (3.82) vs DAG replan ×2 (any_failure) (2.89) — gap 0.93, max σ 0.36 → **MEANINGFUL** (2.6× max stddev)
- **Tools executed / task**: ReAct (3.82) vs DAG replan ×5 (any_failure) (2.88) — gap 0.94, max σ 0.39 → **MEANINGFUL** (2.4× max stddev)
- **Tools executed / task**: ReAct (3.82) vs DAG replan ×5 (empty_synth) (4.72) — gap 0.90, max σ 0.20 → **MEANINGFUL** (4.5× max stddev)
- **Tools executed / task**: ReAct (3.82) vs DAG replan ×2 (empty_synth, top-3) (6.23) — gap 2.42, max σ 0.30 → **MEANINGFUL** (8.2× max stddev)
- **Tools executed / task**: ReAct (3.82) vs DAG replan ×5 (empty_synth, top-3) (6.19) — gap 2.37, max σ 0.66 → **MEANINGFUL** (3.6× max stddev)
- **Tools executed / task**: ReAct (3.82) vs DAG replan aggressive (cap=5, diversif+CoT) (7.23) — gap 3.42, max σ 1.58 → **MEANINGFUL** (2.2× max stddev)
- **Tools executed / task**: ReAct (3.82) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) — gap 5.58, max σ 0.86 → **MEANINGFUL** (6.5× max stddev)
- **Tools executed / task**: ReAct (3.82) vs aggressive − CoT (6.02) — gap 2.20, max σ 0.60 → **MEANINGFUL** (3.7× max stddev)
- **Tools executed / task**: Native parallel (3.97) vs DAG planner (2.66) — gap 1.30, max σ 0.26 → **MEANINGFUL** (4.9× max stddev)
- **Tools executed / task**: Native parallel (3.97) vs DAG replan ×2 (any_failure) (2.89) — gap 1.08, max σ 0.36 → **MEANINGFUL** (3.0× max stddev)
- **Tools executed / task**: Native parallel (3.97) vs DAG replan ×5 (any_failure) (2.88) — gap 1.09, max σ 0.39 → **MEANINGFUL** (2.8× max stddev)
- **Tools executed / task**: Native parallel (3.97) vs DAG replan ×5 (empty_synth) (4.72) — gap 0.75, max σ 0.16 → **MEANINGFUL** (4.8× max stddev)
- **Tools executed / task**: Native parallel (3.97) vs DAG replan ×2 (empty_synth, top-3) (6.23) — gap 2.27, max σ 0.30 → **MEANINGFUL** (7.7× max stddev)
- **Tools executed / task**: Native parallel (3.97) vs DAG replan ×5 (empty_synth, top-3) (6.19) — gap 2.22, max σ 0.66 → **MEANINGFUL** (3.4× max stddev)
- **Tools executed / task**: Native parallel (3.97) vs DAG replan aggressive (cap=5, diversif+CoT) (7.23) — gap 3.27, max σ 1.58 → **MEANINGFUL** (2.1× max stddev)
- **Tools executed / task**: Native parallel (3.97) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) — gap 5.43, max σ 0.86 → **MEANINGFUL** (6.3× max stddev)
- **Tools executed / task**: Native parallel (3.97) vs aggressive − CoT (6.02) — gap 2.05, max σ 0.60 → **MEANINGFUL** (3.4× max stddev)
- **Tools executed / task**: DAG planner (2.66) vs DAG replan ×2 (empty_synth) (3.76) — gap 1.10, max σ 0.31 → **MEANINGFUL** (3.6× max stddev)
- **Tools executed / task**: DAG planner (2.66) vs DAG replan ×5 (empty_synth) (4.72) — gap 2.06, max σ 0.26 → **MEANINGFUL** (7.8× max stddev)
- **Tools executed / task**: DAG planner (2.66) vs DAG replan ×2 (empty_synth, top-3) (6.23) — gap 3.57, max σ 0.30 → **MEANINGFUL** (12.1× max stddev)
- **Tools executed / task**: DAG planner (2.66) vs DAG replan ×5 (empty_synth, top-3) (6.19) — gap 3.53, max σ 0.66 → **MEANINGFUL** (5.3× max stddev)
- **Tools executed / task**: DAG planner (2.66) vs DAG replan aggressive (cap=5, diversif+CoT) (7.23) — gap 4.57, max σ 1.58 → **MEANINGFUL** (2.9× max stddev)
- **Tools executed / task**: DAG planner (2.66) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) — gap 6.74, max σ 0.86 → **MEANINGFUL** (7.8× max stddev)
- **Tools executed / task**: DAG planner (2.66) vs aggressive − diversification (7.31) — gap 4.65, max σ 2.07 → **MEANINGFUL** (2.2× max stddev)
- **Tools executed / task**: DAG planner (2.66) vs aggressive − CoT (6.02) — gap 3.36, max σ 0.60 → **MEANINGFUL** (5.6× max stddev)
- **Tools executed / task**: DAG planner (2.66) vs aggressive − empty_synth (back to any_failure) (5.01) — gap 2.35, max σ 0.65 → **MEANINGFUL** (3.6× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (2.89) vs DAG replan ×2 (empty_synth) (3.76) — gap 0.88, max σ 0.36 → **MEANINGFUL** (2.4× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (2.89) vs DAG replan ×5 (empty_synth) (4.72) — gap 1.83, max σ 0.36 → **MEANINGFUL** (5.1× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (2.89) vs DAG replan ×2 (empty_synth, top-3) (6.23) — gap 3.35, max σ 0.36 → **MEANINGFUL** (9.3× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (2.89) vs DAG replan ×5 (empty_synth, top-3) (6.19) — gap 3.30, max σ 0.66 → **MEANINGFUL** (5.0× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (2.89) vs DAG replan aggressive (cap=5, diversif+CoT) (7.23) — gap 4.35, max σ 1.58 → **MEANINGFUL** (2.8× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (2.89) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) — gap 6.51, max σ 0.86 → **MEANINGFUL** (7.6× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (2.89) vs aggressive − diversification (7.31) — gap 4.43, max σ 2.07 → **MEANINGFUL** (2.1× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (2.89) vs aggressive − CoT (6.02) — gap 3.13, max σ 0.60 → **MEANINGFUL** (5.2× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (2.89) vs aggressive − empty_synth (back to any_failure) (5.01) — gap 2.13, max σ 0.65 → **MEANINGFUL** (3.3× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (2.88) vs DAG replan ×2 (empty_synth) (3.76) — gap 0.88, max σ 0.39 → **MEANINGFUL** (2.2× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (2.88) vs DAG replan ×5 (empty_synth) (4.72) — gap 1.84, max σ 0.39 → **MEANINGFUL** (4.7× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (2.88) vs DAG replan ×2 (empty_synth, top-3) (6.23) — gap 3.36, max σ 0.39 → **MEANINGFUL** (8.5× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (2.88) vs DAG replan ×5 (empty_synth, top-3) (6.19) — gap 3.31, max σ 0.66 → **MEANINGFUL** (5.0× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (2.88) vs DAG replan aggressive (cap=5, diversif+CoT) (7.23) — gap 4.36, max σ 1.58 → **MEANINGFUL** (2.8× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (2.88) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) — gap 6.52, max σ 0.86 → **MEANINGFUL** (7.6× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (2.88) vs aggressive − diversification (7.31) — gap 4.43, max σ 2.07 → **MEANINGFUL** (2.1× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (2.88) vs aggressive − CoT (6.02) — gap 3.14, max σ 0.60 → **MEANINGFUL** (5.2× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (2.88) vs aggressive − empty_synth (back to any_failure) (5.01) — gap 2.13, max σ 0.65 → **MEANINGFUL** (3.3× max stddev)
- **Tools executed / task**: DAG replan ×2 (empty_synth) (3.76) vs DAG replan ×5 (empty_synth) (4.72) — gap 0.96, max σ 0.31 → **MEANINGFUL** (3.1× max stddev)
- **Tools executed / task**: DAG replan ×2 (empty_synth) (3.76) vs DAG replan ×2 (empty_synth, top-3) (6.23) — gap 2.47, max σ 0.31 → **MEANINGFUL** (8.0× max stddev)
- **Tools executed / task**: DAG replan ×2 (empty_synth) (3.76) vs DAG replan ×5 (empty_synth, top-3) (6.19) — gap 2.43, max σ 0.66 → **MEANINGFUL** (3.7× max stddev)
- **Tools executed / task**: DAG replan ×2 (empty_synth) (3.76) vs DAG replan aggressive (cap=5, diversif+CoT) (7.23) — gap 3.47, max σ 1.58 → **MEANINGFUL** (2.2× max stddev)
- **Tools executed / task**: DAG replan ×2 (empty_synth) (3.76) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) — gap 5.64, max σ 0.86 → **MEANINGFUL** (6.5× max stddev)
- **Tools executed / task**: DAG replan ×2 (empty_synth) (3.76) vs aggressive − CoT (6.02) — gap 2.26, max σ 0.60 → **MEANINGFUL** (3.8× max stddev)
- **Tools executed / task**: DAG replan ×5 (empty_synth) (4.72) vs DAG replan ×2 (empty_synth, top-3) (6.23) — gap 1.52, max σ 0.30 → **MEANINGFUL** (5.1× max stddev)
- **Tools executed / task**: DAG replan ×5 (empty_synth) (4.72) vs DAG replan ×5 (empty_synth, top-3) (6.19) — gap 1.47, max σ 0.66 → **MEANINGFUL** (2.2× max stddev)
- **Tools executed / task**: DAG replan ×5 (empty_synth) (4.72) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) — gap 4.68, max σ 0.86 → **MEANINGFUL** (5.4× max stddev)
- **Tools executed / task**: DAG replan ×5 (empty_synth) (4.72) vs aggressive − CoT (6.02) — gap 1.30, max σ 0.60 → **MEANINGFUL** (2.2× max stddev)
- **Tools executed / task**: DAG replan ×2 (empty_synth, top-3) (6.23) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) — gap 3.17, max σ 0.86 → **MEANINGFUL** (3.7× max stddev)
- **Tools executed / task**: DAG replan ×2 (empty_synth, top-3) (6.23) vs aggressive − top-K (back to top-1) (4.02) — gap 2.22, max σ 0.78 → **MEANINGFUL** (2.8× max stddev)
- **Tools executed / task**: DAG replan ×5 (empty_synth, top-3) (6.19) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) — gap 3.21, max σ 0.86 → **MEANINGFUL** (3.7× max stddev)
- **Tools executed / task**: DAG replan ×5 (empty_synth, top-3) (6.19) vs aggressive − top-K (back to top-1) (4.02) — gap 2.17, max σ 0.78 → **MEANINGFUL** (2.8× max stddev)
- **Tools executed / task**: DAG replan aggressive (cap=5, diversif+CoT) (7.23) vs aggressive − top-K (back to top-1) (4.02) — gap 3.22, max σ 1.58 → **MEANINGFUL** (2.0× max stddev)
- **Tools executed / task**: DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) vs aggressive − CoT (6.02) — gap 3.38, max σ 0.86 → **MEANINGFUL** (3.9× max stddev)
- **Tools executed / task**: DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) vs aggressive − top-K (back to top-1) (4.02) — gap 5.38, max σ 0.86 → **MEANINGFUL** (6.2× max stddev)
- **Tools executed / task**: DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (9.40) vs aggressive − empty_synth (back to any_failure) (5.01) — gap 4.39, max σ 0.86 → **MEANINGFUL** (5.1× max stddev)
- **Tools executed / task**: aggressive − CoT (6.02) vs aggressive − top-K (back to top-1) (4.02) — gap 2.00, max σ 0.78 → **MEANINGFUL** (2.6× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG planner ($0.0010) — gap $0.0005 USD, max σ $0.0002 USD → **MEANINGFUL** (2.9× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG replan ×2 (any_failure) ($0.0011) — gap $0.0004 USD, max σ $0.0002 USD → **MEANINGFUL** (2.3× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG replan ×5 (any_failure) ($0.0010) — gap $0.0004 USD, max σ $0.0002 USD → **MEANINGFUL** (2.6× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG replan ×2 (empty_synth, top-3) ($0.0021) — gap $0.0006 USD, max σ $0.0002 USD → **MEANINGFUL** (3.3× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG replan ×5 (empty_synth, top-3) ($0.0021) — gap $0.0006 USD, max σ $0.0003 USD → **MEANINGFUL** (2.1× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) — gap $0.0017 USD, max σ $0.0004 USD → **MEANINGFUL** (4.6× max stddev)
- **Cost / task**: ReAct ($0.0015) vs aggressive − CoT ($0.0022) — gap $0.0007 USD, max σ $0.0002 USD → **MEANINGFUL** (3.4× max stddev)
- **Cost / task**: Native parallel ($0.0015) vs DAG planner ($0.0010) — gap $0.0005 USD, max σ $0.0000 USD → **MEANINGFUL** (11.1× max stddev)
- **Cost / task**: Native parallel ($0.0015) vs DAG replan ×2 (any_failure) ($0.0011) — gap $0.0004 USD, max σ $0.0001 USD → **MEANINGFUL** (3.0× max stddev)
- **Cost / task**: Native parallel ($0.0015) vs DAG replan ×5 (any_failure) ($0.0010) — gap $0.0004 USD, max σ $0.0001 USD → **MEANINGFUL** (4.4× max stddev)
- **Cost / task**: Native parallel ($0.0015) vs DAG replan ×5 (empty_synth) ($0.0018) — gap $0.0003 USD, max σ $0.0001 USD → **MEANINGFUL** (5.3× max stddev)
- **Cost / task**: Native parallel ($0.0015) vs DAG replan ×2 (empty_synth, top-3) ($0.0021) — gap $0.0006 USD, max σ $0.0000 USD → **MEANINGFUL** (13.6× max stddev)
- **Cost / task**: Native parallel ($0.0015) vs DAG replan ×5 (empty_synth, top-3) ($0.0021) — gap $0.0006 USD, max σ $0.0003 USD → **MEANINGFUL** (2.1× max stddev)
- **Cost / task**: Native parallel ($0.0015) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) — gap $0.0017 USD, max σ $0.0004 USD → **MEANINGFUL** (4.7× max stddev)
- **Cost / task**: Native parallel ($0.0015) vs aggressive − CoT ($0.0022) — gap $0.0007 USD, max σ $0.0002 USD → **MEANINGFUL** (3.4× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan ×2 (empty_synth) ($0.0014) — gap $0.0005 USD, max σ $0.0001 USD → **MEANINGFUL** (4.8× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan ×5 (empty_synth) ($0.0018) — gap $0.0008 USD, max σ $0.0001 USD → **MEANINGFUL** (13.8× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan ×2 (empty_synth, top-3) ($0.0021) — gap $0.0011 USD, max σ $0.0000 USD → **MEANINGFUL** (26.9× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan ×5 (empty_synth, top-3) ($0.0021) — gap $0.0011 USD, max σ $0.0003 USD → **MEANINGFUL** (3.7× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0027) — gap $0.0017 USD, max σ $0.0007 USD → **MEANINGFUL** (2.5× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) — gap $0.0022 USD, max σ $0.0004 USD → **MEANINGFUL** (6.0× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs aggressive − diversification ($0.0027) — gap $0.0017 USD, max σ $0.0008 USD → **MEANINGFUL** (2.2× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs aggressive − CoT ($0.0022) — gap $0.0012 USD, max σ $0.0002 USD → **MEANINGFUL** (5.9× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs aggressive − top-K (back to top-1) ($0.0019) — gap $0.0009 USD, max σ $0.0003 USD → **MEANINGFUL** (2.7× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs aggressive − empty_synth (back to any_failure) ($0.0018) — gap $0.0008 USD, max σ $0.0002 USD → **MEANINGFUL** (4.5× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0011) vs DAG replan ×2 (empty_synth) ($0.0014) — gap $0.0003 USD, max σ $0.0001 USD → **MEANINGFUL** (2.8× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0011) vs DAG replan ×5 (empty_synth) ($0.0018) — gap $0.0007 USD, max σ $0.0001 USD → **MEANINGFUL** (5.4× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0011) vs DAG replan ×2 (empty_synth, top-3) ($0.0021) — gap $0.0010 USD, max σ $0.0001 USD → **MEANINGFUL** (7.7× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0011) vs DAG replan ×5 (empty_synth, top-3) ($0.0021) — gap $0.0010 USD, max σ $0.0003 USD → **MEANINGFUL** (3.4× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0011) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0027) — gap $0.0016 USD, max σ $0.0007 USD → **MEANINGFUL** (2.3× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0011) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) — gap $0.0021 USD, max σ $0.0004 USD → **MEANINGFUL** (5.7× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0011) vs aggressive − diversification ($0.0027) — gap $0.0016 USD, max σ $0.0008 USD → **MEANINGFUL** (2.0× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0011) vs aggressive − CoT ($0.0022) — gap $0.0011 USD, max σ $0.0002 USD → **MEANINGFUL** (5.3× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0011) vs aggressive − top-K (back to top-1) ($0.0019) — gap $0.0008 USD, max σ $0.0003 USD → **MEANINGFUL** (2.3× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0011) vs aggressive − empty_synth (back to any_failure) ($0.0018) — gap $0.0007 USD, max σ $0.0002 USD → **MEANINGFUL** (3.9× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs DAG replan ×2 (empty_synth) ($0.0014) — gap $0.0004 USD, max σ $0.0001 USD → **MEANINGFUL** (4.1× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs DAG replan ×5 (empty_synth) ($0.0018) — gap $0.0007 USD, max σ $0.0001 USD → **MEANINGFUL** (7.5× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs DAG replan ×2 (empty_synth, top-3) ($0.0021) — gap $0.0010 USD, max σ $0.0001 USD → **MEANINGFUL** (10.4× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs DAG replan ×5 (empty_synth, top-3) ($0.0021) — gap $0.0011 USD, max σ $0.0003 USD → **MEANINGFUL** (3.6× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0027) — gap $0.0017 USD, max σ $0.0007 USD → **MEANINGFUL** (2.4× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) — gap $0.0021 USD, max σ $0.0004 USD → **MEANINGFUL** (5.9× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs aggressive − diversification ($0.0027) — gap $0.0017 USD, max σ $0.0008 USD → **MEANINGFUL** (2.1× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs aggressive − CoT ($0.0022) — gap $0.0011 USD, max σ $0.0002 USD → **MEANINGFUL** (5.6× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs aggressive − top-K (back to top-1) ($0.0019) — gap $0.0008 USD, max σ $0.0003 USD → **MEANINGFUL** (2.5× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs aggressive − empty_synth (back to any_failure) ($0.0018) — gap $0.0007 USD, max σ $0.0002 USD → **MEANINGFUL** (4.2× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0014) vs DAG replan ×5 (empty_synth) ($0.0018) — gap $0.0003 USD, max σ $0.0001 USD → **MEANINGFUL** (3.5× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0014) vs DAG replan ×2 (empty_synth, top-3) ($0.0021) — gap $0.0006 USD, max σ $0.0001 USD → **MEANINGFUL** (6.4× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0014) vs DAG replan ×5 (empty_synth, top-3) ($0.0021) — gap $0.0007 USD, max σ $0.0003 USD → **MEANINGFUL** (2.2× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0014) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) — gap $0.0017 USD, max σ $0.0004 USD → **MEANINGFUL** (4.8× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0014) vs aggressive − CoT ($0.0022) — gap $0.0007 USD, max σ $0.0002 USD → **MEANINGFUL** (3.6× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0018) vs DAG replan ×2 (empty_synth, top-3) ($0.0021) — gap $0.0003 USD, max σ $0.0001 USD → **MEANINGFUL** (5.0× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0018) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) — gap $0.0014 USD, max σ $0.0004 USD → **MEANINGFUL** (3.8× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth, top-3) ($0.0021) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) — gap $0.0011 USD, max σ $0.0004 USD → **MEANINGFUL** (3.1× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth, top-3) ($0.0021) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) — gap $0.0011 USD, max σ $0.0004 USD → **MEANINGFUL** (2.9× max stddev)
- **Cost / task**: DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) vs aggressive − CoT ($0.0022) — gap $0.0010 USD, max σ $0.0004 USD → **MEANINGFUL** (2.8× max stddev)
- **Cost / task**: DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) vs aggressive − top-K (back to top-1) ($0.0019) — gap $0.0013 USD, max σ $0.0004 USD → **MEANINGFUL** (3.6× max stddev)
- **Cost / task**: DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0032) vs aggressive − empty_synth (back to any_failure) ($0.0018) — gap $0.0014 USD, max σ $0.0004 USD → **MEANINGFUL** (3.9× max stddev)
- **Wall-clock p50**: ReAct (5.7s) vs Native parallel (8.1s) — gap 2.40s, max σ 1.01s → **MEANINGFUL** (2.4× max stddev)
- **Wall-clock p50**: ReAct (5.7s) vs DAG replan ×5 (empty_synth) (8.7s) — gap 3.02s, max σ 0.77s → **MEANINGFUL** (3.9× max stddev)
- **Wall-clock p50**: ReAct (5.7s) vs DAG replan ×2 (empty_synth, top-3) (8.6s) — gap 2.93s, max σ 0.43s → **MEANINGFUL** (6.9× max stddev)
- **Wall-clock p50**: ReAct (5.7s) vs DAG replan ×5 (empty_synth, top-3) (8.8s) — gap 3.15s, max σ 1.37s → **MEANINGFUL** (2.3× max stddev)
- **Wall-clock p50**: ReAct (5.7s) vs DAG replan aggressive (cap=5, diversif+CoT) (11.1s) — gap 5.41s, max σ 2.30s → **MEANINGFUL** (2.4× max stddev)
- **Wall-clock p50**: ReAct (5.7s) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (14.0s) — gap 8.30s, max σ 3.59s → **MEANINGFUL** (2.3× max stddev)
- **Wall-clock p50**: ReAct (5.7s) vs aggressive − diversification (11.6s) — gap 5.94s, max σ 1.52s → **MEANINGFUL** (3.9× max stddev)
- **Wall-clock p50**: ReAct (5.7s) vs aggressive − CoT (9.4s) — gap 3.67s, max σ 1.80s → **MEANINGFUL** (2.0× max stddev)
- **Wall-clock p50**: ReAct (5.7s) vs aggressive − top-K (back to top-1) (7.1s) — gap 1.41s, max σ 0.48s → **MEANINGFUL** (2.9× max stddev)
- **Wall-clock p50**: ReAct (5.7s) vs aggressive − empty_synth (back to any_failure) (9.4s) — gap 3.68s, max σ 1.32s → **MEANINGFUL** (2.8× max stddev)
- **Wall-clock p50**: Native parallel (8.1s) vs DAG replan ×2 (any_failure) (5.7s) — gap 2.38s, max σ 1.01s → **MEANINGFUL** (2.4× max stddev)
- **Wall-clock p50**: Native parallel (8.1s) vs aggressive − diversification (11.6s) — gap 3.54s, max σ 1.52s → **MEANINGFUL** (2.3× max stddev)
- **Wall-clock p50**: DAG planner (6.5s) vs DAG replan ×5 (empty_synth) (8.7s) — gap 2.26s, max σ 0.78s → **MEANINGFUL** (2.9× max stddev)
- **Wall-clock p50**: DAG planner (6.5s) vs DAG replan ×2 (empty_synth, top-3) (8.6s) — gap 2.17s, max σ 0.78s → **MEANINGFUL** (2.8× max stddev)
- **Wall-clock p50**: DAG planner (6.5s) vs DAG replan aggressive (cap=5, diversif+CoT) (11.1s) — gap 4.65s, max σ 2.30s → **MEANINGFUL** (2.0× max stddev)
- **Wall-clock p50**: DAG planner (6.5s) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (14.0s) — gap 7.54s, max σ 3.59s → **MEANINGFUL** (2.1× max stddev)
- **Wall-clock p50**: DAG planner (6.5s) vs aggressive − diversification (11.6s) — gap 5.18s, max σ 1.52s → **MEANINGFUL** (3.4× max stddev)
- **Wall-clock p50**: DAG planner (6.5s) vs aggressive − empty_synth (back to any_failure) (9.4s) — gap 2.92s, max σ 1.32s → **MEANINGFUL** (2.2× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (5.7s) vs DAG replan ×5 (empty_synth) (8.7s) — gap 3.01s, max σ 0.77s → **MEANINGFUL** (3.9× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (5.7s) vs DAG replan ×2 (empty_synth, top-3) (8.6s) — gap 2.92s, max σ 0.41s → **MEANINGFUL** (7.1× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (5.7s) vs DAG replan ×5 (empty_synth, top-3) (8.8s) — gap 3.13s, max σ 1.37s → **MEANINGFUL** (2.3× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (5.7s) vs DAG replan aggressive (cap=5, diversif+CoT) (11.1s) — gap 5.39s, max σ 2.30s → **MEANINGFUL** (2.3× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (5.7s) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (14.0s) — gap 8.28s, max σ 3.59s → **MEANINGFUL** (2.3× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (5.7s) vs aggressive − diversification (11.6s) — gap 5.92s, max σ 1.52s → **MEANINGFUL** (3.9× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (5.7s) vs aggressive − CoT (9.4s) — gap 3.65s, max σ 1.80s → **MEANINGFUL** (2.0× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (5.7s) vs aggressive − top-K (back to top-1) (7.1s) — gap 1.39s, max σ 0.48s → **MEANINGFUL** (2.9× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (5.7s) vs aggressive − empty_synth (back to any_failure) (9.4s) — gap 3.66s, max σ 1.32s → **MEANINGFUL** (2.8× max stddev)
- **Wall-clock p50**: DAG replan ×5 (any_failure) (6.7s) vs DAG replan ×5 (empty_synth) (8.7s) — gap 2.05s, max σ 0.88s → **MEANINGFUL** (2.3× max stddev)
- **Wall-clock p50**: DAG replan ×5 (any_failure) (6.7s) vs DAG replan ×2 (empty_synth, top-3) (8.6s) — gap 1.96s, max σ 0.88s → **MEANINGFUL** (2.2× max stddev)
- **Wall-clock p50**: DAG replan ×5 (any_failure) (6.7s) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (14.0s) — gap 7.32s, max σ 3.59s → **MEANINGFUL** (2.0× max stddev)
- **Wall-clock p50**: DAG replan ×5 (any_failure) (6.7s) vs aggressive − diversification (11.6s) — gap 4.96s, max σ 1.52s → **MEANINGFUL** (3.3× max stddev)
- **Wall-clock p50**: DAG replan ×5 (any_failure) (6.7s) vs aggressive − empty_synth (back to any_failure) (9.4s) — gap 2.71s, max σ 1.32s → **MEANINGFUL** (2.1× max stddev)
- **Wall-clock p50**: DAG replan ×2 (empty_synth) (6.4s) vs DAG replan aggressive (cap=5, diversif+CoT) (11.1s) — gap 4.71s, max σ 2.30s → **MEANINGFUL** (2.0× max stddev)
- **Wall-clock p50**: DAG replan ×2 (empty_synth) (6.4s) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (14.0s) — gap 7.60s, max σ 3.59s → **MEANINGFUL** (2.1× max stddev)
- **Wall-clock p50**: DAG replan ×2 (empty_synth) (6.4s) vs aggressive − diversification (11.6s) — gap 5.24s, max σ 1.86s → **MEANINGFUL** (2.8× max stddev)
- **Wall-clock p50**: DAG replan ×5 (empty_synth) (8.7s) vs aggressive − top-K (back to top-1) (7.1s) — gap 1.62s, max σ 0.77s → **MEANINGFUL** (2.1× max stddev)
- **Wall-clock p50**: DAG replan ×2 (empty_synth, top-3) (8.6s) vs aggressive − top-K (back to top-1) (7.1s) — gap 1.53s, max σ 0.48s → **MEANINGFUL** (3.2× max stddev)
- **Wall-clock p50**: aggressive − diversification (11.6s) vs aggressive − top-K (back to top-1) (7.1s) — gap 4.53s, max σ 1.52s → **MEANINGFUL** (3.0× max stddev)

### HotpotQA (comparison — inherently parallel)

- **Accuracy**: DAG planner (81.1pp) vs DAG replan ×2 (empty_synth, top-3) (88.9pp) — gap 7.78pp, max σ 1.92pp → **MEANINGFUL** (4.0× max stddev)
- **Accuracy**: DAG replan ×2 (any_failure) (80.0pp) vs DAG replan ×2 (empty_synth, top-3) (88.9pp) — gap 8.89pp, max σ 3.33pp → **MEANINGFUL** (2.7× max stddev)
- **Accuracy**: DAG replan ×2 (empty_synth) (82.2pp) vs DAG replan ×2 (empty_synth, top-3) (88.9pp) — gap 6.67pp, max σ 1.92pp → **MEANINGFUL** (3.5× max stddev)
- **Accuracy**: DAG replan ×5 (empty_synth) (77.8pp) vs DAG replan ×2 (empty_synth, top-3) (88.9pp) — gap 11.11pp, max σ 3.85pp → **MEANINGFUL** (2.9× max stddev)
- **Accuracy**: DAG replan ×5 (empty_synth) (77.8pp) vs DAG replan aggressive (cap=5, diversif+CoT) (85.6pp) — gap 7.78pp, max σ 3.85pp → **MEANINGFUL** (2.0× max stddev)
- **Accuracy**: DAG replan ×5 (empty_synth) (77.8pp) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (85.6pp) — gap 7.78pp, max σ 3.85pp → **MEANINGFUL** (2.0× max stddev)
- **Accuracy**: DAG replan ×2 (empty_synth, top-3) (88.9pp) vs DAG replan ×5 (empty_synth, top-3) (83.3pp) — gap 5.56pp, max σ 1.92pp → **MEANINGFUL** (2.9× max stddev)
- **LLM calls / task**: ReAct (4.97) vs Native parallel (4.38) — gap 0.58, max σ 0.09 → **MEANINGFUL** (6.4× max stddev)
- **LLM calls / task**: ReAct (4.97) vs DAG planner (2.00) — gap 2.97, max σ 0.09 → **MEANINGFUL** (32.7× max stddev)
- **LLM calls / task**: ReAct (4.97) vs DAG replan ×2 (any_failure) (2.01) — gap 2.95, max σ 0.09 → **MEANINGFUL** (32.5× max stddev)
- **LLM calls / task**: ReAct (4.97) vs DAG replan ×5 (any_failure) (2.00) — gap 2.97, max σ 0.09 → **MEANINGFUL** (32.7× max stddev)
- **LLM calls / task**: ReAct (4.97) vs DAG replan ×2 (empty_synth) (2.25) — gap 2.72, max σ 0.09 → **MEANINGFUL** (29.9× max stddev)
- **LLM calls / task**: ReAct (4.97) vs DAG replan ×5 (empty_synth) (2.20) — gap 2.77, max σ 0.23 → **MEANINGFUL** (12.1× max stddev)
- **LLM calls / task**: ReAct (4.97) vs DAG replan ×2 (empty_synth, top-3) (2.27) — gap 2.70, max σ 0.20 → **MEANINGFUL** (13.5× max stddev)
- **LLM calls / task**: ReAct (4.97) vs DAG replan ×5 (empty_synth, top-3) (2.27) — gap 2.70, max σ 0.13 → **MEANINGFUL** (20.2× max stddev)
- **LLM calls / task**: ReAct (4.97) vs DAG replan aggressive (cap=5, diversif+CoT) (2.18) — gap 2.78, max σ 0.09 → **MEANINGFUL** (30.6× max stddev)
- **LLM calls / task**: ReAct (4.97) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.07) — gap 2.90, max σ 0.09 → **MEANINGFUL** (31.9× max stddev)
- **LLM calls / task**: ReAct (4.97) vs aggressive − CoT (2.35) — gap 2.62, max σ 0.18 → **MEANINGFUL** (14.2× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs DAG planner (2.00) — gap 2.38, max σ 0.06 → **MEANINGFUL** (41.8× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs DAG replan ×2 (any_failure) (2.01) — gap 2.37, max σ 0.06 → **MEANINGFUL** (41.6× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs DAG replan ×5 (any_failure) (2.00) — gap 2.38, max σ 0.06 → **MEANINGFUL** (41.8× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs DAG replan ×2 (empty_synth) (2.25) — gap 2.13, max σ 0.08 → **MEANINGFUL** (25.5× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs DAG replan ×5 (empty_synth) (2.20) — gap 2.18, max σ 0.23 → **MEANINGFUL** (9.6× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs DAG replan ×2 (empty_synth, top-3) (2.27) — gap 2.11, max σ 0.20 → **MEANINGFUL** (10.6× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs DAG replan ×5 (empty_synth, top-3) (2.27) — gap 2.11, max σ 0.13 → **MEANINGFUL** (15.9× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs DAG replan aggressive (cap=5, diversif+CoT) (2.18) — gap 2.20, max σ 0.09 → **MEANINGFUL** (25.0× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.07) — gap 2.31, max σ 0.07 → **MEANINGFUL** (34.7× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs aggressive − CoT (2.35) — gap 2.03, max σ 0.18 → **MEANINGFUL** (11.0× max stddev)
- **LLM calls / task**: DAG planner (2.00) vs DAG replan ×5 (any_failure) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG planner (2.00) vs DAG replan ×2 (empty_synth) (2.25) — gap 0.25, max σ 0.08 → **MEANINGFUL** (3.0× max stddev)
- **LLM calls / task**: DAG planner (2.00) vs DAG replan ×5 (empty_synth, top-3) (2.27) — gap 0.27, max σ 0.13 → **MEANINGFUL** (2.0× max stddev)
- **LLM calls / task**: DAG planner (2.00) vs DAG replan aggressive (cap=5, diversif+CoT) (2.18) — gap 0.18, max σ 0.09 → **MEANINGFUL** (2.1× max stddev)
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.01) vs DAG replan ×2 (empty_synth) (2.25) — gap 0.24, max σ 0.08 → **MEANINGFUL** (2.8× max stddev)
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.00) vs DAG replan ×2 (empty_synth) (2.25) — gap 0.25, max σ 0.08 → **MEANINGFUL** (3.0× max stddev)
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.00) vs DAG replan ×5 (empty_synth, top-3) (2.27) — gap 0.27, max σ 0.13 → **MEANINGFUL** (2.0× max stddev)
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.00) vs DAG replan aggressive (cap=5, diversif+CoT) (2.18) — gap 0.18, max σ 0.09 → **MEANINGFUL** (2.1× max stddev)
- **LLM calls / task**: DAG replan ×2 (empty_synth) (2.25) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.07) — gap 0.18, max σ 0.08 → **MEANINGFUL** (2.2× max stddev)
- **Tools executed / task**: ReAct (3.98) vs DAG replan ×2 (empty_synth, top-3) (6.31) — gap 2.33, max σ 0.84 → **MEANINGFUL** (2.8× max stddev)
- **Tools executed / task**: ReAct (3.98) vs DAG replan ×5 (empty_synth, top-3) (5.77) — gap 1.79, max σ 0.81 → **MEANINGFUL** (2.2× max stddev)
- **Tools executed / task**: ReAct (3.98) vs aggressive − CoT (6.07) — gap 2.10, max σ 0.48 → **MEANINGFUL** (4.4× max stddev)
- **Tools executed / task**: Native parallel (4.09) vs DAG planner (3.82) — gap 0.27, max σ 0.13 → **MEANINGFUL** (2.0× max stddev)
- **Tools executed / task**: Native parallel (4.09) vs DAG replan ×2 (empty_synth, top-3) (6.31) — gap 2.22, max σ 0.84 → **MEANINGFUL** (2.6× max stddev)
- **Tools executed / task**: Native parallel (4.09) vs DAG replan ×5 (empty_synth, top-3) (5.77) — gap 1.68, max σ 0.81 → **MEANINGFUL** (2.1× max stddev)
- **Tools executed / task**: Native parallel (4.09) vs aggressive − CoT (6.07) — gap 1.98, max σ 0.48 → **MEANINGFUL** (4.1× max stddev)
- **Tools executed / task**: DAG planner (3.82) vs DAG replan ×2 (empty_synth) (4.16) — gap 0.34, max σ 0.06 → **MEANINGFUL** (6.1× max stddev)
- **Tools executed / task**: DAG planner (3.82) vs DAG replan ×2 (empty_synth, top-3) (6.31) — gap 2.49, max σ 0.84 → **MEANINGFUL** (3.0× max stddev)
- **Tools executed / task**: DAG planner (3.82) vs DAG replan ×5 (empty_synth, top-3) (5.77) — gap 1.95, max σ 0.81 → **MEANINGFUL** (2.4× max stddev)
- **Tools executed / task**: DAG planner (3.82) vs DAG replan aggressive (cap=5, diversif+CoT) (5.28) — gap 1.46, max σ 0.69 → **MEANINGFUL** (2.1× max stddev)
- **Tools executed / task**: DAG planner (3.82) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (6.90) — gap 3.08, max σ 1.46 → **MEANINGFUL** (2.1× max stddev)
- **Tools executed / task**: DAG planner (3.82) vs aggressive − CoT (6.07) — gap 2.25, max σ 0.48 → **MEANINGFUL** (4.7× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (3.89) vs DAG replan ×2 (empty_synth) (4.16) — gap 0.27, max σ 0.08 → **MEANINGFUL** (3.4× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (3.89) vs DAG replan ×2 (empty_synth, top-3) (6.31) — gap 2.42, max σ 0.84 → **MEANINGFUL** (2.9× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (3.89) vs DAG replan ×5 (empty_synth, top-3) (5.77) — gap 1.88, max σ 0.81 → **MEANINGFUL** (2.3× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (3.89) vs DAG replan aggressive (cap=5, diversif+CoT) (5.28) — gap 1.39, max σ 0.69 → **MEANINGFUL** (2.0× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (3.89) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (6.90) — gap 3.01, max σ 1.46 → **MEANINGFUL** (2.1× max stddev)
- **Tools executed / task**: DAG replan ×2 (any_failure) (3.89) vs aggressive − CoT (6.07) — gap 2.19, max σ 0.48 → **MEANINGFUL** (4.6× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (3.86) vs DAG replan ×2 (empty_synth, top-3) (6.31) — gap 2.46, max σ 0.84 → **MEANINGFUL** (2.9× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (3.86) vs DAG replan ×5 (empty_synth, top-3) (5.77) — gap 1.91, max σ 0.81 → **MEANINGFUL** (2.4× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (3.86) vs DAG replan aggressive (cap=5, diversif+CoT) (5.28) — gap 1.42, max σ 0.69 → **MEANINGFUL** (2.1× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (3.86) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (6.90) — gap 3.04, max σ 1.46 → **MEANINGFUL** (2.1× max stddev)
- **Tools executed / task**: DAG replan ×5 (any_failure) (3.86) vs aggressive − CoT (6.07) — gap 2.22, max σ 0.48 → **MEANINGFUL** (4.6× max stddev)
- **Tools executed / task**: DAG replan ×2 (empty_synth) (4.16) vs DAG replan ×2 (empty_synth, top-3) (6.31) — gap 2.15, max σ 0.84 → **MEANINGFUL** (2.6× max stddev)
- **Tools executed / task**: DAG replan ×2 (empty_synth) (4.16) vs aggressive − CoT (6.07) — gap 1.92, max σ 0.48 → **MEANINGFUL** (4.0× max stddev)
- **Tools executed / task**: DAG replan ×5 (empty_synth) (4.12) vs DAG replan ×2 (empty_synth, top-3) (6.31) — gap 2.19, max σ 0.84 → **MEANINGFUL** (2.6× max stddev)
- **Tools executed / task**: DAG replan ×5 (empty_synth) (4.12) vs DAG replan ×5 (empty_synth, top-3) (5.77) — gap 1.65, max σ 0.81 → **MEANINGFUL** (2.0× max stddev)
- **Tools executed / task**: DAG replan ×5 (empty_synth) (4.12) vs aggressive − CoT (6.07) — gap 1.96, max σ 0.48 → **MEANINGFUL** (4.1× max stddev)
- **Cost / task**: ReAct ($0.0015) vs Native parallel ($0.0013) — gap $0.0002 USD, max σ $0.0001 USD → **MEANINGFUL** (2.7× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG planner ($0.0011) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (11.8× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG replan ×2 (any_failure) ($0.0012) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (11.4× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG replan ×5 (any_failure) ($0.0012) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (8.1× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG replan ×2 (empty_synth) ($0.0013) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (6.4× max stddev)
- **Cost / task**: ReAct ($0.0015) vs aggressive − CoT ($0.0018) — gap $0.0004 USD, max σ $0.0001 USD → **MEANINGFUL** (2.5× max stddev)
- **Cost / task**: Native parallel ($0.0013) vs DAG replan ×2 (empty_synth, top-3) ($0.0018) — gap $0.0006 USD, max σ $0.0003 USD → **MEANINGFUL** (2.2× max stddev)
- **Cost / task**: Native parallel ($0.0013) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0018) — gap $0.0005 USD, max σ $0.0002 USD → **MEANINGFUL** (2.5× max stddev)
- **Cost / task**: Native parallel ($0.0013) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0021) — gap $0.0008 USD, max σ $0.0003 USD → **MEANINGFUL** (2.3× max stddev)
- **Cost / task**: Native parallel ($0.0013) vs aggressive − CoT ($0.0018) — gap $0.0005 USD, max σ $0.0001 USD → **MEANINGFUL** (3.7× max stddev)
- **Cost / task**: DAG planner ($0.0011) vs DAG replan ×2 (empty_synth) ($0.0013) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (4.4× max stddev)
- **Cost / task**: DAG planner ($0.0011) vs DAG replan ×2 (empty_synth, top-3) ($0.0018) — gap $0.0007 USD, max σ $0.0003 USD → **MEANINGFUL** (2.7× max stddev)
- **Cost / task**: DAG planner ($0.0011) vs DAG replan ×5 (empty_synth, top-3) ($0.0018) — gap $0.0006 USD, max σ $0.0003 USD → **MEANINGFUL** (2.1× max stddev)
- **Cost / task**: DAG planner ($0.0011) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0018) — gap $0.0006 USD, max σ $0.0002 USD → **MEANINGFUL** (3.2× max stddev)
- **Cost / task**: DAG planner ($0.0011) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0021) — gap $0.0009 USD, max σ $0.0003 USD → **MEANINGFUL** (2.7× max stddev)
- **Cost / task**: DAG planner ($0.0011) vs aggressive − CoT ($0.0018) — gap $0.0007 USD, max σ $0.0001 USD → **MEANINGFUL** (4.6× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0012) vs DAG replan ×2 (empty_synth) ($0.0013) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (3.9× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0012) vs DAG replan ×2 (empty_synth, top-3) ($0.0018) — gap $0.0007 USD, max σ $0.0003 USD → **MEANINGFUL** (2.6× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0012) vs DAG replan ×5 (empty_synth, top-3) ($0.0018) — gap $0.0006 USD, max σ $0.0003 USD → **MEANINGFUL** (2.0× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0012) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0018) — gap $0.0006 USD, max σ $0.0002 USD → **MEANINGFUL** (3.1× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0012) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0021) — gap $0.0009 USD, max σ $0.0003 USD → **MEANINGFUL** (2.7× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0012) vs aggressive − CoT ($0.0018) — gap $0.0007 USD, max σ $0.0001 USD → **MEANINGFUL** (4.5× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0012) vs DAG replan ×2 (empty_synth) ($0.0013) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (3.2× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0012) vs DAG replan ×2 (empty_synth, top-3) ($0.0018) — gap $0.0007 USD, max σ $0.0003 USD → **MEANINGFUL** (2.6× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0012) vs DAG replan ×5 (empty_synth, top-3) ($0.0018) — gap $0.0006 USD, max σ $0.0003 USD → **MEANINGFUL** (2.0× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0012) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0018) — gap $0.0006 USD, max σ $0.0002 USD → **MEANINGFUL** (3.2× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0012) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0021) — gap $0.0009 USD, max σ $0.0003 USD → **MEANINGFUL** (2.7× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0012) vs aggressive − CoT ($0.0018) — gap $0.0007 USD, max σ $0.0001 USD → **MEANINGFUL** (4.5× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0013) vs DAG replan ×2 (empty_synth, top-3) ($0.0018) — gap $0.0006 USD, max σ $0.0003 USD → **MEANINGFUL** (2.2× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0013) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0018) — gap $0.0005 USD, max σ $0.0002 USD → **MEANINGFUL** (2.5× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0013) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0021) — gap $0.0008 USD, max σ $0.0003 USD → **MEANINGFUL** (2.3× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0013) vs aggressive − CoT ($0.0018) — gap $0.0005 USD, max σ $0.0001 USD → **MEANINGFUL** (3.7× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0013) vs DAG replan ×2 (empty_synth, top-3) ($0.0018) — gap $0.0006 USD, max σ $0.0003 USD → **MEANINGFUL** (2.2× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0013) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0018) — gap $0.0005 USD, max σ $0.0002 USD → **MEANINGFUL** (2.6× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0013) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0021) — gap $0.0008 USD, max σ $0.0003 USD → **MEANINGFUL** (2.4× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0013) vs aggressive − CoT ($0.0018) — gap $0.0006 USD, max σ $0.0001 USD → **MEANINGFUL** (3.8× max stddev)
- **Wall-clock p50**: Native parallel (6.4s) vs DAG planner (4.6s) — gap 1.82s, max σ 0.48s → **MEANINGFUL** (3.8× max stddev)
- **Wall-clock p50**: Native parallel (6.4s) vs DAG replan ×2 (any_failure) (4.7s) — gap 1.73s, max σ 0.48s → **MEANINGFUL** (3.6× max stddev)
- **Wall-clock p50**: Native parallel (6.4s) vs DAG replan ×5 (any_failure) (5.0s) — gap 1.45s, max σ 0.48s → **MEANINGFUL** (3.0× max stddev)
- **Wall-clock p50**: Native parallel (6.4s) vs DAG replan ×2 (empty_synth) (4.6s) — gap 1.78s, max σ 0.48s → **MEANINGFUL** (3.7× max stddev)
- **Wall-clock p50**: Native parallel (6.4s) vs DAG replan ×5 (empty_synth) (5.0s) — gap 1.41s, max σ 0.49s → **MEANINGFUL** (2.9× max stddev)
- **Wall-clock p50**: Native parallel (6.4s) vs DAG replan ×5 (empty_synth, top-3) (5.4s) — gap 1.05s, max σ 0.48s → **MEANINGFUL** (2.2× max stddev)
- **Wall-clock p50**: DAG planner (4.6s) vs DAG replan ×2 (empty_synth, top-3) (5.7s) — gap 1.10s, max σ 0.37s → **MEANINGFUL** (3.0× max stddev)
- **Wall-clock p50**: DAG planner (4.6s) vs DAG replan ×5 (empty_synth, top-3) (5.4s) — gap 0.78s, max σ 0.29s → **MEANINGFUL** (2.7× max stddev)
- **Wall-clock p50**: DAG planner (4.6s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.6s) — gap 1.06s, max σ 0.13s → **MEANINGFUL** (8.0× max stddev)
- **Wall-clock p50**: DAG planner (4.6s) vs aggressive − CoT (5.5s) — gap 0.89s, max σ 0.42s → **MEANINGFUL** (2.1× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (4.7s) vs DAG replan ×2 (empty_synth, top-3) (5.7s) — gap 1.01s, max σ 0.37s → **MEANINGFUL** (2.7× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (4.7s) vs DAG replan ×5 (empty_synth, top-3) (5.4s) — gap 0.69s, max σ 0.29s → **MEANINGFUL** (2.4× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (4.7s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.6s) — gap 0.97s, max σ 0.21s → **MEANINGFUL** (4.7× max stddev)
- **Wall-clock p50**: DAG replan ×2 (empty_synth) (4.6s) vs DAG replan ×2 (empty_synth, top-3) (5.7s) — gap 1.05s, max σ 0.37s → **MEANINGFUL** (2.8× max stddev)
- **Wall-clock p50**: DAG replan ×2 (empty_synth) (4.6s) vs DAG replan ×5 (empty_synth, top-3) (5.4s) — gap 0.73s, max σ 0.29s → **MEANINGFUL** (2.5× max stddev)
- **Wall-clock p50**: DAG replan ×2 (empty_synth) (4.6s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.6s) — gap 1.01s, max σ 0.13s → **MEANINGFUL** (7.7× max stddev)

### GitHub (structurally predictable multi-entity)

- **Accuracy**: Native parallel (100.0pp) vs DAG replan ×5 (empty_synth) (96.0pp) — gap 4.00pp, max σ 0.00pp → MEANINGFUL (zero stddev on one side)
- **Accuracy**: Native parallel (100.0pp) vs DAG replan aggressive (cap=5, diversif+CoT) (94.7pp) — gap 5.33pp, max σ 2.31pp → **MEANINGFUL** (2.3× max stddev)
- **LLM calls / task**: ReAct (3.84) vs Native parallel (2.40) — gap 1.44, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs DAG planner (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs DAG replan ×2 (any_failure) (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs DAG replan ×5 (any_failure) (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs DAG replan ×2 (empty_synth) (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs DAG replan ×5 (empty_synth) (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs DAG replan ×2 (empty_synth, top-3) (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs DAG replan ×5 (empty_synth, top-3) (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs DAG replan aggressive (cap=5, diversif+CoT) (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs aggressive − CoT (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs DAG planner (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs DAG replan ×2 (any_failure) (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs DAG replan ×5 (any_failure) (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs DAG replan ×2 (empty_synth) (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs DAG replan ×5 (empty_synth) (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs DAG replan ×2 (empty_synth, top-3) (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs DAG replan ×5 (empty_synth, top-3) (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs DAG replan aggressive (cap=5, diversif+CoT) (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs aggressive − CoT (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: DAG planner (2.00) vs DAG replan ×2 (any_failure) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG planner (2.00) vs DAG replan ×5 (any_failure) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG planner (2.00) vs DAG replan ×2 (empty_synth) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG planner (2.00) vs DAG replan ×5 (empty_synth) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG planner (2.00) vs DAG replan ×2 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG planner (2.00) vs DAG replan ×5 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG planner (2.00) vs DAG replan aggressive (cap=5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG planner (2.00) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG planner (2.00) vs aggressive − CoT (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.00) vs DAG replan ×5 (any_failure) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.00) vs DAG replan ×2 (empty_synth) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.00) vs DAG replan ×5 (empty_synth) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.00) vs DAG replan ×2 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.00) vs DAG replan ×5 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.00) vs DAG replan aggressive (cap=5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.00) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (any_failure) (2.00) vs aggressive − CoT (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.00) vs DAG replan ×2 (empty_synth) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.00) vs DAG replan ×5 (empty_synth) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.00) vs DAG replan ×2 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.00) vs DAG replan ×5 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.00) vs DAG replan aggressive (cap=5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.00) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (any_failure) (2.00) vs aggressive − CoT (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (empty_synth) (2.00) vs DAG replan ×5 (empty_synth) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (empty_synth) (2.00) vs DAG replan ×2 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (empty_synth) (2.00) vs DAG replan ×5 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (empty_synth) (2.00) vs DAG replan aggressive (cap=5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (empty_synth) (2.00) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (empty_synth) (2.00) vs aggressive − CoT (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (empty_synth) (2.00) vs DAG replan ×2 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (empty_synth) (2.00) vs DAG replan ×5 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (empty_synth) (2.00) vs DAG replan aggressive (cap=5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (empty_synth) (2.00) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (empty_synth) (2.00) vs aggressive − CoT (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (empty_synth, top-3) (2.00) vs DAG replan ×5 (empty_synth, top-3) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (empty_synth, top-3) (2.00) vs DAG replan aggressive (cap=5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (empty_synth, top-3) (2.00) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×2 (empty_synth, top-3) (2.00) vs aggressive − CoT (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (empty_synth, top-3) (2.00) vs DAG replan aggressive (cap=5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (empty_synth, top-3) (2.00) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan ×5 (empty_synth, top-3) (2.00) vs aggressive − CoT (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan aggressive (cap=5, diversif+CoT) (2.00) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan aggressive (cap=5, diversif+CoT) (2.00) vs aggressive − CoT (2.00) — gap 0.00, max σ 0.00 → tied
- **LLM calls / task**: DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.00) vs aggressive − CoT (2.00) — gap 0.00, max σ 0.00 → tied
- **Tools executed / task**: ReAct (2.84) vs Native parallel (2.84) — gap 0.00, max σ 0.00 → tied
- **Tools executed / task**: ReAct (2.84) vs DAG planner (3.03) — gap 0.19, max σ 0.02 → **MEANINGFUL** (8.1× max stddev)
- **Tools executed / task**: ReAct (2.84) vs DAG replan ×2 (any_failure) (2.97) — gap 0.13, max σ 0.05 → **MEANINGFUL** (2.9× max stddev)
- **Tools executed / task**: ReAct (2.84) vs DAG replan ×2 (empty_synth) (3.01) — gap 0.17, max σ 0.02 → **MEANINGFUL** (7.5× max stddev)
- **Tools executed / task**: ReAct (2.84) vs DAG replan ×5 (empty_synth) (2.99) — gap 0.15, max σ 0.06 → **MEANINGFUL** (2.4× max stddev)
- **Tools executed / task**: ReAct (2.84) vs DAG replan ×2 (empty_synth, top-3) (3.04) — gap 0.20, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **Tools executed / task**: ReAct (2.84) vs DAG replan ×5 (empty_synth, top-3) (3.00) — gap 0.16, max σ 0.04 → **MEANINGFUL** (3.8× max stddev)
- **Tools executed / task**: ReAct (2.84) vs DAG replan aggressive (cap=5, diversif+CoT) (3.00) — gap 0.16, max σ 0.07 → **MEANINGFUL** (2.3× max stddev)
- **Tools executed / task**: ReAct (2.84) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.99) — gap 0.15, max σ 0.06 → **MEANINGFUL** (2.4× max stddev)
- **Tools executed / task**: ReAct (2.84) vs aggressive − CoT (3.03) — gap 0.19, max σ 0.02 → **MEANINGFUL** (10.7× max stddev)
- **Tools executed / task**: Native parallel (2.84) vs DAG planner (3.03) — gap 0.19, max σ 0.02 → **MEANINGFUL** (8.1× max stddev)
- **Tools executed / task**: Native parallel (2.84) vs DAG replan ×2 (any_failure) (2.97) — gap 0.13, max σ 0.05 → **MEANINGFUL** (2.9× max stddev)
- **Tools executed / task**: Native parallel (2.84) vs DAG replan ×2 (empty_synth) (3.01) — gap 0.17, max σ 0.02 → **MEANINGFUL** (7.5× max stddev)
- **Tools executed / task**: Native parallel (2.84) vs DAG replan ×5 (empty_synth) (2.99) — gap 0.15, max σ 0.06 → **MEANINGFUL** (2.4× max stddev)
- **Tools executed / task**: Native parallel (2.84) vs DAG replan ×2 (empty_synth, top-3) (3.04) — gap 0.20, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **Tools executed / task**: Native parallel (2.84) vs DAG replan ×5 (empty_synth, top-3) (3.00) — gap 0.16, max σ 0.04 → **MEANINGFUL** (3.8× max stddev)
- **Tools executed / task**: Native parallel (2.84) vs DAG replan aggressive (cap=5, diversif+CoT) (3.00) — gap 0.16, max σ 0.07 → **MEANINGFUL** (2.3× max stddev)
- **Tools executed / task**: Native parallel (2.84) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (2.99) — gap 0.15, max σ 0.06 → **MEANINGFUL** (2.4× max stddev)
- **Tools executed / task**: Native parallel (2.84) vs aggressive − CoT (3.03) — gap 0.19, max σ 0.02 → **MEANINGFUL** (10.7× max stddev)
- **Cost / task**: ReAct ($0.0012) vs Native parallel ($0.0008) — gap $0.0004 USD, max σ $0.0000 USD → **MEANINGFUL** (60.8× max stddev)
- **Cost / task**: ReAct ($0.0012) vs DAG planner ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (28.6× max stddev)
- **Cost / task**: ReAct ($0.0012) vs DAG replan ×2 (any_failure) ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (17.9× max stddev)
- **Cost / task**: ReAct ($0.0012) vs DAG replan ×5 (any_failure) ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (18.9× max stddev)
- **Cost / task**: ReAct ($0.0012) vs DAG replan ×2 (empty_synth) ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (27.7× max stddev)
- **Cost / task**: ReAct ($0.0012) vs DAG replan ×5 (empty_synth) ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (16.6× max stddev)
- **Cost / task**: ReAct ($0.0012) vs DAG replan ×2 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (18.7× max stddev)
- **Cost / task**: ReAct ($0.0012) vs DAG replan ×5 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (14.8× max stddev)
- **Cost / task**: ReAct ($0.0012) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0013) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (5.0× max stddev)
- **Cost / task**: ReAct ($0.0012) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0013) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (4.4× max stddev)
- **Cost / task**: ReAct ($0.0012) vs aggressive − CoT ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (19.2× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs DAG planner ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (66.7× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs DAG replan ×2 (any_failure) ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (19.3× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs DAG replan ×5 (any_failure) ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (19.8× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs DAG replan ×2 (empty_synth) ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (68.5× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs DAG replan ×5 (empty_synth) ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (18.7× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs DAG replan ×2 (empty_synth, top-3) ($0.0011) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (87.2× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs DAG replan ×5 (empty_synth, top-3) ($0.0011) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (30.6× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0013) — gap $0.0005 USD, max σ $0.0000 USD → **MEANINGFUL** (29.5× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0013) — gap $0.0005 USD, max σ $0.0000 USD → **MEANINGFUL** (26.0× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs aggressive − CoT ($0.0011) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (69.3× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan ×2 (empty_synth) ($0.0010) — gap $0.0000 USD, max σ $0.0000 USD → **MEANINGFUL** (2.6× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan ×2 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (32.7× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan ×5 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (6.5× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0013) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (16.5× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0013) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (14.6× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs aggressive − CoT ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (15.7× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0010) vs DAG replan ×2 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (6.4× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0010) vs DAG replan ×5 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (5.7× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0010) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0013) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (16.8× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0010) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0013) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (14.8× max stddev)
- **Cost / task**: DAG replan ×2 (any_failure) ($0.0010) vs aggressive − CoT ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (6.1× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs DAG replan ×2 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (7.0× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs DAG replan ×5 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (6.3× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0013) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (17.0× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0013) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (15.0× max stddev)
- **Cost / task**: DAG replan ×5 (any_failure) ($0.0010) vs aggressive − CoT ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (6.7× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0010) vs DAG replan ×2 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (26.8× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0010) vs DAG replan ×5 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (5.9× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0010) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0013) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (16.2× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0010) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0013) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (14.3× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth) ($0.0010) vs aggressive − CoT ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (14.2× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0010) vs DAG replan ×2 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (5.7× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0010) vs DAG replan ×5 (empty_synth, top-3) ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (5.1× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0010) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0013) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (16.5× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0010) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0013) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (14.6× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth) ($0.0010) vs aggressive − CoT ($0.0011) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (5.5× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth, top-3) ($0.0011) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0013) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (12.5× max stddev)
- **Cost / task**: DAG replan ×2 (empty_synth, top-3) ($0.0011) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0013) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (11.1× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth, top-3) ($0.0011) vs DAG replan aggressive (cap=5, diversif+CoT) ($0.0013) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (13.0× max stddev)
- **Cost / task**: DAG replan ×5 (empty_synth, top-3) ($0.0011) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0013) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (11.5× max stddev)
- **Cost / task**: DAG replan aggressive (cap=5, diversif+CoT) ($0.0013) vs aggressive − CoT ($0.0011) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (12.7× max stddev)
- **Cost / task**: DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) ($0.0013) vs aggressive − CoT ($0.0011) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (11.3× max stddev)
- **Wall-clock p50**: ReAct (4.4s) vs Native parallel (3.5s) — gap 0.86s, max σ 0.25s → **MEANINGFUL** (3.5× max stddev)
- **Wall-clock p50**: ReAct (4.4s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.0s) — gap 0.66s, max σ 0.25s → **MEANINGFUL** (2.7× max stddev)
- **Wall-clock p50**: Native parallel (3.5s) vs DAG planner (4.2s) — gap 0.68s, max σ 0.23s → **MEANINGFUL** (3.0× max stddev)
- **Wall-clock p50**: Native parallel (3.5s) vs DAG replan ×2 (any_failure) (4.2s) — gap 0.68s, max σ 0.23s → **MEANINGFUL** (3.0× max stddev)
- **Wall-clock p50**: Native parallel (3.5s) vs DAG replan ×5 (any_failure) (4.4s) — gap 0.85s, max σ 0.25s → **MEANINGFUL** (3.3× max stddev)
- **Wall-clock p50**: Native parallel (3.5s) vs DAG replan ×2 (empty_synth) (4.5s) — gap 0.95s, max σ 0.21s → **MEANINGFUL** (4.6× max stddev)
- **Wall-clock p50**: Native parallel (3.5s) vs DAG replan ×5 (empty_synth) (4.3s) — gap 0.82s, max σ 0.24s → **MEANINGFUL** (3.4× max stddev)
- **Wall-clock p50**: Native parallel (3.5s) vs DAG replan ×2 (empty_synth, top-3) (4.4s) — gap 0.87s, max σ 0.17s → **MEANINGFUL** (5.0× max stddev)
- **Wall-clock p50**: Native parallel (3.5s) vs DAG replan ×5 (empty_synth, top-3) (4.3s) — gap 0.84s, max σ 0.17s → **MEANINGFUL** (4.9× max stddev)
- **Wall-clock p50**: Native parallel (3.5s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.0s) — gap 1.53s, max σ 0.17s → **MEANINGFUL** (8.8× max stddev)
- **Wall-clock p50**: Native parallel (3.5s) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (5.5s) — gap 1.96s, max σ 0.59s → **MEANINGFUL** (3.4× max stddev)
- **Wall-clock p50**: DAG planner (4.2s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.0s) — gap 0.84s, max σ 0.23s → **MEANINGFUL** (3.7× max stddev)
- **Wall-clock p50**: DAG planner (4.2s) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (5.5s) — gap 1.28s, max σ 0.59s → **MEANINGFUL** (2.2× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (4.2s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.0s) — gap 0.84s, max σ 0.23s → **MEANINGFUL** (3.7× max stddev)
- **Wall-clock p50**: DAG replan ×2 (any_failure) (4.2s) vs DAG replan max (cap=8, any_or_empty, top-5, diversif+CoT) (5.5s) — gap 1.28s, max σ 0.59s → **MEANINGFUL** (2.2× max stddev)
- **Wall-clock p50**: DAG replan ×5 (any_failure) (4.4s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.0s) — gap 0.68s, max σ 0.25s → **MEANINGFUL** (2.7× max stddev)
- **Wall-clock p50**: DAG replan ×2 (empty_synth) (4.5s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.0s) — gap 0.57s, max σ 0.21s → **MEANINGFUL** (2.8× max stddev)
- **Wall-clock p50**: DAG replan ×5 (empty_synth) (4.3s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.0s) — gap 0.71s, max σ 0.24s → **MEANINGFUL** (2.9× max stddev)
- **Wall-clock p50**: DAG replan ×2 (empty_synth, top-3) (4.4s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.0s) — gap 0.65s, max σ 0.12s → **MEANINGFUL** (5.6× max stddev)
- **Wall-clock p50**: DAG replan ×5 (empty_synth, top-3) (4.3s) vs DAG replan aggressive (cap=5, diversif+CoT) (5.0s) — gap 0.69s, max σ 0.10s → **MEANINGFUL** (7.2× max stddev)

### BFCL v4 parallel (function-call accuracy, AST judge)

- **Accuracy**: ReAct (82.2pp) vs DAG replan ×5 (empty_synth, top-3) (75.6pp) — gap 6.67pp, max σ 1.92pp → **MEANINGFUL** (3.5× max stddev)
- **Accuracy**: ReAct (82.2pp) vs aggressive − CoT (75.6pp) — gap 6.67pp, max σ 1.92pp → **MEANINGFUL** (3.5× max stddev)
- **Accuracy**: Native parallel (83.3pp) vs DAG replan ×5 (empty_synth, top-3) (75.6pp) — gap 7.78pp, max σ 1.92pp → **MEANINGFUL** (4.0× max stddev)
- **Accuracy**: Native parallel (83.3pp) vs aggressive − CoT (75.6pp) — gap 7.78pp, max σ 1.92pp → **MEANINGFUL** (4.0× max stddev)
- **LLM calls / task**: ReAct (3.69) vs Native parallel (2.20) — gap 1.49, max σ 0.09 → **MEANINGFUL** (17.2× max stddev)
- **LLM calls / task**: ReAct (3.69) vs DAG planner (2.00) — gap 1.69, max σ 0.06 → **MEANINGFUL** (28.3× max stddev)
- **LLM calls / task**: ReAct (3.69) vs DAG replan ×5 (empty_synth, top-3) (3.28) — gap 0.41, max σ 0.06 → **MEANINGFUL** (6.9× max stddev)
- **LLM calls / task**: Native parallel (2.20) vs DAG planner (2.00) — gap 0.20, max σ 0.09 → **MEANINGFUL** (2.3× max stddev)
- **LLM calls / task**: Native parallel (2.20) vs DAG replan ×5 (empty_synth, top-3) (3.28) — gap 1.08, max σ 0.09 → **MEANINGFUL** (12.5× max stddev)
- **LLM calls / task**: Native parallel (2.20) vs aggressive − CoT (3.29) — gap 1.09, max σ 0.51 → **MEANINGFUL** (2.1× max stddev)
- **LLM calls / task**: DAG planner (2.00) vs DAG replan ×5 (empty_synth, top-3) (3.28) — gap 1.28, max σ 0.05 → **MEANINGFUL** (25.1× max stddev)
- **LLM calls / task**: DAG planner (2.00) vs aggressive − CoT (3.29) — gap 1.29, max σ 0.51 → **MEANINGFUL** (2.5× max stddev)
- **Tools executed / task**: ReAct (2.69) vs DAG replan ×5 (empty_synth, top-3) (4.44) — gap 1.75, max σ 0.24 → **MEANINGFUL** (7.4× max stddev)
- **Tools executed / task**: ReAct (2.69) vs aggressive − CoT (4.27) — gap 1.58, max σ 0.58 → **MEANINGFUL** (2.7× max stddev)
- **Tools executed / task**: Native parallel (2.83) vs DAG replan ×5 (empty_synth, top-3) (4.44) — gap 1.62, max σ 0.24 → **MEANINGFUL** (6.8× max stddev)
- **Tools executed / task**: Native parallel (2.83) vs aggressive − CoT (4.27) — gap 1.44, max σ 0.58 → **MEANINGFUL** (2.5× max stddev)
- **Tools executed / task**: DAG planner (2.70) vs DAG replan ×5 (empty_synth, top-3) (4.44) — gap 1.74, max σ 0.24 → **MEANINGFUL** (7.4× max stddev)
- **Tools executed / task**: DAG planner (2.70) vs aggressive − CoT (4.27) — gap 1.57, max σ 0.58 → **MEANINGFUL** (2.7× max stddev)
- **Cost / task**: ReAct ($0.0007) vs Native parallel ($0.0006) — gap $0.0001 USD, max σ $0.0000 USD → **MEANINGFUL** (10.0× max stddev)
- **Cost / task**: ReAct ($0.0007) vs DAG planner ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (27.8× max stddev)
- **Cost / task**: ReAct ($0.0007) vs DAG replan ×5 (empty_synth, top-3) ($0.0018) — gap $0.0011 USD, max σ $0.0001 USD → **MEANINGFUL** (18.7× max stddev)
- **Cost / task**: ReAct ($0.0007) vs aggressive − CoT ($0.0017) — gap $0.0010 USD, max σ $0.0003 USD → **MEANINGFUL** (3.5× max stddev)
- **Cost / task**: Native parallel ($0.0006) vs DAG planner ($0.0010) — gap $0.0004 USD, max σ $0.0000 USD → **MEANINGFUL** (26.6× max stddev)
- **Cost / task**: Native parallel ($0.0006) vs DAG replan ×5 (empty_synth, top-3) ($0.0018) — gap $0.0012 USD, max σ $0.0001 USD → **MEANINGFUL** (21.2× max stddev)
- **Cost / task**: Native parallel ($0.0006) vs aggressive − CoT ($0.0017) — gap $0.0011 USD, max σ $0.0003 USD → **MEANINGFUL** (4.1× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs DAG replan ×5 (empty_synth, top-3) ($0.0018) — gap $0.0008 USD, max σ $0.0001 USD → **MEANINGFUL** (14.5× max stddev)
- **Cost / task**: DAG planner ($0.0010) vs aggressive − CoT ($0.0017) — gap $0.0008 USD, max σ $0.0003 USD → **MEANINGFUL** (2.7× max stddev)
- **Wall-clock p50**: ReAct (4.7s) vs Native parallel (3.4s) — gap 1.36s, max σ 0.19s → **MEANINGFUL** (7.0× max stddev)
- **Wall-clock p50**: Native parallel (3.4s) vs DAG planner (4.3s) — gap 0.96s, max σ 0.22s → **MEANINGFUL** (4.5× max stddev)
