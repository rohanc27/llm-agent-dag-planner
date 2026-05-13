# Failure-mode breakdown

Each cell is the **percentage of that strategy's failures** falling into the named category. Rightmost column is the total failure count (over all benchmarks × seeds, deduped to latest row per task).

| Strategy | PLAN_VALIDATION_ERROR | JUDGE_DISPUTED | HEDGED_DESPITE_EVIDENCE | HEDGED_REFUSAL | WRONG_FIRST_RETRIEVAL | OTHER | Failures | Tasks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dag_planner | 9.5% (8) | 19.0% (16) | — | 31.0% (26) | 38.1% (32) | 2.4% (2) | 84 | 255 |
| dag_replan_aggressive | 4.5% (3) | 14.9% (10) | — | 4.5% (3) | 70.1% (47) | 6.0% (4) | 67 | 255 |
| dag_replan_aggressive_no_cot | 7.9% (5) | 20.6% (13) | — | 7.9% (5) | 63.5% (40) | — | 63 | 255 |
| dag_replan_aggressive_no_diversify | 7.1% (1) | 14.3% (2) | — | 7.1% (1) | 64.3% (9) | 7.1% (1) | 14 | 30 |
| dag_replan_aggressive_no_emptysynth | 15.8% (3) | 5.3% (1) | — | 21.1% (4) | 57.9% (11) | — | 19 | 30 |
| dag_replan_aggressive_no_topk | 11.8% (2) | 17.6% (3) | — | — | 64.7% (11) | 5.9% (1) | 17 | 30 |
| dag_replan_cap2 | 9.3% (7) | 25.3% (19) | — | 26.7% (20) | 38.7% (29) | — | 75 | 255 |
| dag_replan_cap2_empty | 10.4% (7) | 17.9% (12) | — | 10.4% (7) | 58.2% (39) | 3.0% (2) | 67 | 255 |
| dag_replan_cap2_empty_top3 | 7.9% (5) | 19.0% (12) | — | 6.3% (4) | 66.7% (42) | — | 63 | 255 |
| dag_replan_cap5 | 5.9% (5) | 24.7% (21) | — | 28.2% (24) | 38.8% (33) | 2.4% (2) | 85 | 255 |
| dag_replan_cap5_empty | 9.9% (7) | 23.9% (17) | — | 8.5% (6) | 52.1% (37) | 5.6% (4) | 71 | 255 |
| dag_replan_cap5_empty_top3 | 5.9% (4) | 23.5% (16) | — | 8.8% (6) | 57.4% (39) | 4.4% (3) | 68 | 255 |
| dag_replan_max | 50.0% (1) | — | — | — | — | 50.0% (1) | 2 | 3 |
| native_parallel | — | 20.4% (10) | — | 4.1% (2) | 61.2% (30) | 14.3% (7) | 49 | 255 |
| react | — | 19.6% (10) | — | 5.9% (3) | 62.7% (32) | 11.8% (6) | 51 | 255 |
