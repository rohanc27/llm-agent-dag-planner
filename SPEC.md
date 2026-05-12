# SPEC: llm-agent-dag-planner

> **Repo:** https://github.com/rohanc27/llm-agent-dag-planner

## 0. One-paragraph project description

A benchmark study comparing three strategies for orchestrating LLM tool calls — sequential ReAct, native parallel tool-use (the LLM returns multiple tool calls per turn), and explicit DAG-based planning (a re-implementation of LLMCompiler, Kim et al. ICML 2024) — evaluated on three benchmarks: HotpotQA (multi-hop Wikipedia QA), the BFCL v3 parallel subset (Berkeley Function Calling Leaderboard), and a custom GitHub-API benchmark designed by us. All three strategies use the same underlying LLM (Claude Sonnet) and the same tool implementations. We report latency, tokens, cost, and accuracy. The central research question: with 2026-era models that already support native parallel tool-use, does explicit DAG planning still provide latency and cost advantages, and on which task patterns?

## 1. Stack

- **Language:** Python 3.11+
- **LLM:** Claude Sonnet 4 (via `anthropic` SDK) — same model for all three strategies
- **Tool-use:** Claude's native tool-use API
- **Concurrency:** `asyncio` with `anthropic.AsyncAnthropic`
- **Eval framework:** custom, no LangChain/LangGraph in v1 (keep code transparent and short)
- **Reference:** LLMCompiler paper (arXiv:2312.04511, ICML 2024) — cite in README

## 2. Repository structure

```
llm-agent-dag-planner/
├── README.md                  # final write-up (last step)
├── SPEC.md                    # this file
├── requirements.txt
├── .env.example               # ANTHROPIC_API_KEY, GITHUB_TOKEN (optional)
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── llm.py                 # Claude client wrapper with instrumentation
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py            # Tool dataclass / registry
│   │   ├── wikipedia.py       # Wikipedia search + fetch (HotpotQA)
│   │   ├── github.py          # GitHub API tools (custom benchmark)
│   │   └── bfcl_tools.py      # BFCL function definitions
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── react.py           # Sequential ReAct loop
│   │   ├── native_parallel.py # Claude's built-in parallel tool calls
│   │   └── dag_planner.py     # LLMCompiler-style DAG planner + executor
│   ├── metrics.py             # Instrumentation: latency, tokens, cost, calls
│   ├── judge.py               # LLM-as-judge for HotpotQA answer correctness
│   └── run_eval.py            # Main entrypoint
├── benchmarks/
│   ├── hotpotqa/
│   │   ├── load.py            # Download + sample HotpotQA dev set
│   │   └── tasks.json         # 30 sampled tasks (committed for reproducibility)
│   ├── bfcl/
│   │   ├── load.py            # Pull BFCL parallel subset from their repo
│   │   └── tasks.json
│   └── github/
│       └── tasks.json         # 25 hand-crafted tasks (you write these)
├── results/
│   ├── results.json           # Raw run data
│   └── results.md             # Final results tables
└── scripts/
    └── plot_results.py        # Optional: latency/cost plots
```

## 3. Build order (CRITICAL — do not deviate)

Build in this order. Each step ends with a runnable component. **Do not start the DAG planner until everything before it works. After completing each step, STOP and wait for the user to verify before moving to the next step.**

### Step 1: `llm.py` — instrumented LLM wrapper

`CallLLM` class wrapping `anthropic.AsyncAnthropic`. Every call records:
- `latency_seconds` (wall clock)
- `input_tokens`, `output_tokens` (from response.usage)
- `cost_usd` (computed from current Claude Sonnet 4 pricing — put pricing in a constant)
- `n_tool_calls` (count of tool_use blocks in response)

Returns the response plus a `CallMetrics` dataclass.

### Step 2: `tools/base.py` + `tools/wikipedia.py`

`Tool` dataclass: `name`, `description`, `input_schema` (JSON schema dict), `execute` (async function).

Wikipedia tools:
- `wikipedia_search(query: str) -> list[str]` — returns top-5 article titles via Wikipedia API
- `wikipedia_fetch(title: str) -> str` — returns first 500 words of article body

Use `https://en.wikipedia.org/w/api.php` — free, no auth. Use `httpx.AsyncClient` for async.

### Step 3: `strategies/react.py` — sequential ReAct baseline

The standard loop:
```
while not done and steps < MAX_STEPS:
    response = await llm.call(messages, tools=tool_defs)
    if response.stop_reason == "end_turn":
        return final answer
    for tool_use in response.tool_use_blocks:
        result = await tool.execute(tool_use.input)
        append result to messages
```

IMPORTANT: Force sequential by passing `disable_parallel_tool_use=True` to Claude (the param exists in the API — verify in docs). If only one tool call per turn is allowed, this is true ReAct.

Returns: `(final_answer: str, aggregate_metrics: AggregateMetrics)`.

### Step 4: `benchmarks/hotpotqa/load.py` + sample 30 tasks

Download HotpotQA dev set from `https://hotpotqa.github.io/`. Filter for `"type": "bridge"` (multi-hop), sample 30 deterministically (seed=42). Save to `tasks.json`. Schema:
```json
{"id": "...", "question": "...", "answer": "...", "supporting_facts": [...]}
```

### Step 5: `judge.py` — LLM judge for answer correctness

For HotpotQA: an LLM (Claude Sonnet, separate call) is given the question, gold answer, and predicted answer. Returns `{"correct": bool, "rationale": str}`. Use prompt that emphasizes semantic equivalence (HotpotQA answers are short spans).

### Step 6: `run_eval.py` — first runnable end-to-end

Run ReAct on the 30 HotpotQA tasks, judge each, output:
```
Strategy: react
Benchmark: hotpotqa
Accuracy: X/30 (Y%)
Mean latency: Z.Zs (p50: ..., p95: ...)
Mean tokens: ...
Mean cost: $0.0X
Mean tool calls: ...
```

**At this point you have a working evaluation pipeline. Everything from here adds new strategies and benchmarks.**

### Step 7: `strategies/native_parallel.py`

Same loop as ReAct, but `disable_parallel_tool_use=False`. Claude can return multiple tool_use blocks per response; execute them concurrently with `asyncio.gather`. This is the "free" parallel baseline.

Run on HotpotQA. Compare numbers to ReAct.

### Step 8: `strategies/dag_planner.py` — the main contribution

LLMCompiler-style planner. Two-phase:

**Phase A — Plan generation.** Single LLM call. Use a special "submit_plan" tool with this input schema:
```json
{
  "type": "object",
  "properties": {
    "tasks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "integer"},
          "tool": {"type": "string"},
          "args": {"type": "object"},
          "depends_on": {"type": "array", "items": {"type": "integer"}}
        },
        "required": ["id", "tool", "args", "depends_on"]
      }
    }
  }
}
```

Args can reference outputs of prior tasks via the placeholder `"$task_<id>"`. The planner sees all the regular tools as descriptions in its system prompt but cannot call them — only `submit_plan`. This separates planning from execution.

**Phase B — Execution.** Topological sort the DAG. For each level, execute tasks concurrently with `asyncio.gather`. Substitute `"$task_<id>"` placeholders with prior outputs.

After execution, one final "synthesis" LLM call gets the question + all tool outputs and produces the final answer.

Total LLM calls: 2 (plan + synthesis). Compare to ReAct (N calls for N steps) and native parallel (typically 2-3 calls).

Run on HotpotQA. You now have all three strategies on one benchmark.

### Step 9: `tools/github.py` + `benchmarks/github/tasks.json`

GitHub tools (all use `https://api.github.com`, unauth gets 60 req/hr — enough for eval, but using a `GITHUB_TOKEN` raises it to 5000/hr):
- `github_get_repo(owner, repo)` → stars, forks, language, description
- `github_get_latest_release(owner, repo)` → tag, date, name
- `github_get_top_contributors(owner, repo, n=5)` → list
- `github_get_open_issues(owner, repo)` → count
- `github_search_repos(query)` → list of top-10 matching repos

Write 25 tasks by hand. Aim for variety:
- ~10 "embarrassingly parallel": "Get stars and latest release for repos A, B, C, D"
- ~10 "mixed": "Find top Rust repos, then get top contributors of each"
- ~5 "control / sequential": "Find top-starred ML repo, then check its latest release" (must be sequential)

Format: `{"id": "gh_01", "question": "...", "answer": "...", "answer_type": "list|count|name", "tools_required": [...]}`.

For accuracy: most answers should be deterministic (counts, names) so you can do exact-match judging. Add an `answer_type` field to drive the judge.

### Step 10: BFCL parallel subset

Clone `https://github.com/ShishirPatil/gorilla` (BFCL is under `berkeley-function-call-leaderboard/`). Pull only the `parallel_function` category. Each entry has: question, function definitions, expected calls (in AST form).

For BFCL, accuracy is "did the strategy emit the right set of tool calls?" — *not* end-to-end answer. So you need a special eval mode: run the strategy with the BFCL functions as no-op stubs that just log what was called, then compare the called set against the expected set (AST-equivalent).

This benchmark *specifically* measures whether each strategy correctly identifies parallelism opportunities.

### Step 11: Final eval run + results

Run all 3 strategies × 3 benchmarks = 9 cells. Write `results.md` with:
- Big results table (rows: strategy × benchmark, cols: accuracy, latency p50/p95, tokens, cost, n_llm_calls)
- A scatter plot: latency vs. accuracy across all 9 cells
- A breakdown by task type on GitHub benchmark (parallel-friendly vs. sequential tasks)
- Discussion section: when does DAG planning win? When does native parallel suffice? When is ReAct still competitive?

### Step 12: README

Sections:
1. **TL;DR with headline numbers**
2. **Motivation** — cite the LLMCompiler paper, note that the field has moved on (native parallel tool-use is now standard); reproducing and extending is timely.
3. **Methods** — three strategies, with a diagram (Mermaid is fine).
4. **Benchmarks** — HotpotQA, BFCL parallel, GitHub custom.
5. **Results** — the table + plot.
6. **Findings** — 2-3 bullet points stating what you learned.
7. **Reproducibility** — `pip install -r requirements.txt && python -m src.run_eval --all`.
8. **Limitations** — small N per benchmark, single LLM family tested.
9. **References** — LLMCompiler paper, BFCL paper, HotpotQA paper.

## 4. Pricing constants (current as of build date)

Put in `src/llm.py`:
```python
# Claude Sonnet 4 pricing — verify with current docs before final eval
INPUT_COST_PER_MTOK = 3.00   # $3 per million input tokens
OUTPUT_COST_PER_MTOK = 15.00 # $15 per million output tokens
```
Verify against current Anthropic pricing docs before running the final eval.

## 5. What "done for the day" looks like

Minimum viable end-of-day:
- Steps 1-6 complete (ReAct on HotpotQA working end-to-end with metrics)
- Step 7 complete (native parallel comparison)
- Step 8 partially working (DAG planner runs on at least 3 tasks correctly)

Stretch:
- Step 8 fully passing on HotpotQA
- Started Step 9 (GitHub tools defined)

Reserve weekend 2 for: GitHub benchmark, BFCL integration, polish, README, plots.

## 6. Resume bullet target

> Re-implemented LLMCompiler (ICML 2024) DAG-based parallel function calling using Claude Sonnet 4 tool-use; benchmarked it against ReAct and native parallel tool-use on HotpotQA, BFCL v3 parallel subset, and a custom GitHub API benchmark — measured [X.Y]x latency speedup, [Z]% cost reduction, and [+W]pp accuracy improvement over ReAct at parity with native parallel on simple cases.

## 7. Anti-goals (don't do these today)

- LangChain, LangGraph, LlamaIndex — adds setup tax, hides the technique
- Caching layers, observability dashboards — weekend 2 polish
- Cloud deployment — weekend 2
- Multiple LLM providers — single-provider study is fine and cleaner
- Optimizing the planner prompt past v1 — get the system working first

## 8. Notes for Claude Code

- Use `asyncio` throughout. No threading.
- Use `pydantic` for data classes if you want validation; `dataclasses` is fine.
- Use `httpx` (async) for HTTP, not `requests`.
- Use `python-dotenv` for `.env` loading.
- Use `rich` for prettier eval output (optional).
- Pin versions in `requirements.txt`.
- Write small unit tests for the DAG topological sort and the `$task_N` substitution — these are the parts most likely to have bugs.
- Don't write tests for the LLM calls themselves; they're integration-tested by the eval.
- **After each Step, STOP and wait for the user to verify before moving to the next Step.**

## 9. Reference papers/repos

- LLMCompiler: arXiv:2312.04511, github.com/SqueezeAILab/LLMCompiler
- HotpotQA: arXiv:1809.09600, hotpotqa.github.io
- BFCL: gorilla.cs.berkeley.edu/leaderboard.html, github.com/ShishirPatil/gorilla
- ReAct: arXiv:2210.03629
