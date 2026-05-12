# Multi-seed eval — mean ± stddev across seeds

Each cell aggregates per-seed scalars (one accuracy / mean-LLM-calls etc. per seed) across seeds. Stddev is the sample stddev of those per-seed values — not the within-seed variance. `±—` means only one seed is present.

## HotpotQA (bridge — adaptive 2-hop)

_Seeds: [7, 17, 42]; n per seed: 30._

| Metric | ReAct | Native parallel | DAG planner |
| --- | --- | --- | --- |
| Accuracy | 57.8% ± 7.7pp | 61.1% ± 11.7pp | 28.9% ± 13.5pp |
| LLM calls / task | 4.79 ± 0.18 | 4.93 ± 0.04 | 1.91 ± 0.02 |
| Tools executed / task | 3.82 ± 0.20 | 3.97 ± 0.06 | 2.66 ± 0.26 |
| Cost / task | $0.0015 ± $0.0002 | $0.0015 ± $0.0000 | $0.0010 ± $0.0000 |
| Wall-clock p50 | 5.63s ± 0.39s | 8.10s ± 1.01s | 6.46s ± 0.78s |
| Wall-clock mean | 7.69s ± 0.96s | 9.73s ± 0.55s | 7.86s ± 0.40s |
| Errors (total) | 1.0 ± 1.7 | 0.3 ± 0.6 | 1.0 ± 1.0 |

## HotpotQA (comparison — inherently parallel)

_Seeds: [7, 17, 42]; n per seed: 30._

| Metric | ReAct | Native parallel | DAG planner |
| --- | --- | --- | --- |
| Accuracy | 86.7% ± 5.8pp | 84.4% ± 8.4pp | 81.1% ± 1.9pp |
| LLM calls / task | 4.97 ± 0.09 | 4.38 ± 0.06 | 2.00 ± 0.00 |
| Tools executed / task | 3.98 ± 0.10 | 4.09 ± 0.13 | 3.82 ± 0.06 |
| Cost / task | $0.0015 ± $0.0000 | $0.0013 ± $0.0001 | $0.0011 ± $0.0000 |
| Wall-clock p50 | 5.49s ± 0.76s | 6.40s ± 0.48s | 4.58s ± 0.10s |
| Wall-clock mean | 6.71s ± 0.66s | 6.97s ± 0.19s | 4.95s ± 0.46s |
| Errors (total) | 0.7 ± 0.6 | 1.0 ± 1.7 | 0.3 ± 0.6 |

## GitHub (structurally predictable multi-entity)

_Seeds: [7, 17, 42]; n per seed: 25._

| Metric | ReAct | Native parallel | DAG planner |
| --- | --- | --- | --- |
| Accuracy | 98.7% ± 2.3pp | 100.0% ± 0.0pp | 96.0% ± 4.0pp |
| LLM calls / task | 3.84 ± 0.00 | 2.40 ± 0.00 | 2.00 ± 0.00 |
| Tools executed / task | 2.84 ± 0.00 | 2.84 ± 0.00 | 3.03 ± 0.02 |
| Cost / task | $0.0012 ± $0.0000 | $0.0008 ± $0.0000 | $0.0010 ± $0.0000 |
| Wall-clock p50 | 4.37s ± 0.25s | 3.51s ± 0.17s | 4.19s ± 0.23s |
| Wall-clock mean | 4.28s ± 0.14s | 3.76s ± 0.10s | 4.45s ± 0.09s |
| Errors (total) | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |

## Statistically meaningful differences

A pairwise gap is flagged **MEANINGFUL** when `|mean_a − mean_b| ≥ 2 × max(stddev_a, stddev_b)` — i.e. the two means are at least 2 stddevs apart on the wider of the two error bars. Cells with only one seed are skipped (no stddev defined).

### HotpotQA (bridge — adaptive 2-hop)

- **Accuracy**: ReAct (57.8pp) vs DAG planner (28.9pp) — gap 28.89pp, max σ 13.47pp → **MEANINGFUL** (2.1× max stddev)
- **Accuracy**: Native parallel (61.1pp) vs DAG planner (28.9pp) — gap 32.22pp, max σ 13.47pp → **MEANINGFUL** (2.4× max stddev)
- **LLM calls / task**: ReAct (4.79) vs DAG planner (1.91) — gap 2.89, max σ 0.18 → **MEANINGFUL** (15.7× max stddev)
- **LLM calls / task**: Native parallel (4.93) vs DAG planner (1.91) — gap 3.02, max σ 0.04 → **MEANINGFUL** (86.2× max stddev)
- **Tools executed / task**: ReAct (3.82) vs DAG planner (2.66) — gap 1.16, max σ 0.26 → **MEANINGFUL** (4.4× max stddev)
- **Tools executed / task**: Native parallel (3.97) vs DAG planner (2.66) — gap 1.30, max σ 0.26 → **MEANINGFUL** (4.9× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG planner ($0.0010) — gap $0.0005 USD, max σ $0.0002 USD → **MEANINGFUL** (2.9× max stddev)
- **Cost / task**: Native parallel ($0.0015) vs DAG planner ($0.0010) — gap $0.0005 USD, max σ $0.0000 USD → **MEANINGFUL** (11.1× max stddev)
- **Wall-clock p50**: ReAct (5.6s) vs Native parallel (8.1s) — gap 2.46s, max σ 1.01s → **MEANINGFUL** (2.4× max stddev)

### HotpotQA (comparison — inherently parallel)

- **LLM calls / task**: ReAct (4.97) vs Native parallel (4.38) — gap 0.58, max σ 0.09 → **MEANINGFUL** (6.4× max stddev)
- **LLM calls / task**: ReAct (4.97) vs DAG planner (2.00) — gap 2.97, max σ 0.09 → **MEANINGFUL** (32.7× max stddev)
- **LLM calls / task**: Native parallel (4.38) vs DAG planner (2.00) — gap 2.38, max σ 0.06 → **MEANINGFUL** (41.8× max stddev)
- **Tools executed / task**: Native parallel (4.09) vs DAG planner (3.82) — gap 0.27, max σ 0.13 → **MEANINGFUL** (2.0× max stddev)
- **Cost / task**: ReAct ($0.0015) vs Native parallel ($0.0013) — gap $0.0002 USD, max σ $0.0001 USD → **MEANINGFUL** (2.7× max stddev)
- **Cost / task**: ReAct ($0.0015) vs DAG planner ($0.0011) — gap $0.0003 USD, max σ $0.0000 USD → **MEANINGFUL** (11.8× max stddev)
- **Wall-clock p50**: Native parallel (6.4s) vs DAG planner (4.6s) — gap 1.82s, max σ 0.48s → **MEANINGFUL** (3.8× max stddev)

### GitHub (structurally predictable multi-entity)

- **LLM calls / task**: ReAct (3.84) vs Native parallel (2.40) — gap 1.44, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: ReAct (3.84) vs DAG planner (2.00) — gap 1.84, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **LLM calls / task**: Native parallel (2.40) vs DAG planner (2.00) — gap 0.40, max σ 0.00 → MEANINGFUL (zero stddev on one side)
- **Tools executed / task**: ReAct (2.84) vs Native parallel (2.84) — gap 0.00, max σ 0.00 → tied
- **Tools executed / task**: ReAct (2.84) vs DAG planner (3.03) — gap 0.19, max σ 0.02 → **MEANINGFUL** (8.1× max stddev)
- **Tools executed / task**: Native parallel (2.84) vs DAG planner (3.03) — gap 0.19, max σ 0.02 → **MEANINGFUL** (8.1× max stddev)
- **Cost / task**: ReAct ($0.0012) vs Native parallel ($0.0008) — gap $0.0004 USD, max σ $0.0000 USD → **MEANINGFUL** (60.8× max stddev)
- **Cost / task**: ReAct ($0.0012) vs DAG planner ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (28.6× max stddev)
- **Cost / task**: Native parallel ($0.0008) vs DAG planner ($0.0010) — gap $0.0002 USD, max σ $0.0000 USD → **MEANINGFUL** (66.7× max stddev)
- **Wall-clock p50**: ReAct (4.4s) vs Native parallel (3.5s) — gap 0.86s, max σ 0.25s → **MEANINGFUL** (3.5× max stddev)
- **Wall-clock p50**: Native parallel (3.5s) vs DAG planner (4.2s) — gap 0.68s, max σ 0.23s → **MEANINGFUL** (3.0× max stddev)
