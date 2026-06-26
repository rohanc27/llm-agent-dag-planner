# Failure-mode breakdown

Each cell is the **percentage of that strategy's failures** falling into the named category. Rightmost column is the total failure count (over all benchmarks × seeds, deduped to latest row per task).

| Strategy | PLAN_VALIDATION_ERROR | JUDGE_DISPUTED | HEDGED_DESPITE_EVIDENCE | HEDGED_REFUSAL | WRONG_FIRST_RETRIEVAL | OTHER | Failures | Tasks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dag_planner | 7.5% (8) | 15.1% (16) | — | 34.9% (37) | 40.6% (43) | 1.9% (2) | 106 | 345 |
| dag_replan_aggressive | 4.5% (3) | 14.9% (10) | — | 4.5% (3) | 70.1% (47) | 6.0% (4) | 67 | 255 |
| dag_replan_aggressive_no_cot | 6.9% (9) | 15.3% (20) | — | 13.7% (18) | 64.1% (84) | — | 131 | 515 |
| dag_replan_aggressive_no_diversify | 2.2% (1) | 15.6% (7) | — | 11.1% (5) | 68.9% (31) | 2.2% (1) | 45 | 90 |
| dag_replan_aggressive_no_emptysynth | 9.4% (5) | 5.7% (3) | — | 26.4% (14) | 58.5% (31) | — | 53 | 90 |
| dag_replan_aggressive_no_topk | 23.1% (12) | 7.7% (4) | — | 1.9% (1) | 65.4% (34) | 1.9% (1) | 52 | 90 |
| dag_replan_cap2 | 9.3% (7) | 25.3% (19) | — | 26.7% (20) | 38.7% (29) | — | 75 | 255 |
| dag_replan_cap2_empty | 10.4% (7) | 17.9% (12) | — | 10.4% (7) | 58.2% (39) | 3.0% (2) | 67 | 255 |
| dag_replan_cap2_empty_top3 | 7.9% (5) | 19.0% (12) | — | 6.3% (4) | 66.7% (42) | — | 63 | 255 |
| dag_replan_cap5 | 5.9% (5) | 24.7% (21) | — | 28.2% (24) | 38.8% (33) | 2.4% (2) | 85 | 255 |
| dag_replan_cap5_empty | 9.9% (7) | 23.9% (17) | — | 8.5% (6) | 52.1% (37) | 5.6% (4) | 71 | 255 |
| dag_replan_cap5_empty_top3 | 4.4% (4) | 17.8% (16) | — | 12.2% (11) | 62.2% (56) | 3.3% (3) | 90 | 345 |
| dag_replan_max | 8.6% (5) | 5.2% (3) | — | 5.2% (3) | 81.0% (47) | — | 58 | 255 |
| native_parallel | — | 15.6% (10) | — | 4.7% (3) | 64.1% (41) | 15.6% (10) | 64 | 345 |
| react | — | 14.9% (10) | — | 4.5% (3) | 67.2% (45) | 13.4% (9) | 67 | 345 |
