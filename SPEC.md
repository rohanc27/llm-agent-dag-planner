# SPEC: llm-agent-dag-planner

> **Repo:** https://github.com/rohanc27/llm-agent-dag-planner

## 0. One-paragraph project description

A benchmark study comparing strategies for orchestrating LLM tool calls — sequential ReAct, native parallel tool-use, and explicit DAG-based planning (re-implementing LLMCompiler, Kim et al. ICML 2024 from scratch and additionally as LangGraph and Google ADK variants) — evaluated on HotpotQA (multi-hop Wikipedia QA), the BFCL v3 parallel subset (Berkeley Function Calling Leaderboard), and a custom GitHub-API benchmark we design. All strategies use the same LLM provider abstraction. **Gemini 2.5 Flash on Google AI Studio is the primary provider; Claude Sonnet 4.6 is added in Weekend 3 as a cross-provider validation run.** We report latency, tokens, cost, and accuracy. The system is fully instrumented with OpenTelemetry, with Langfuse for LLM-specific observability and Cloud Trace for distributed tracing, and the eval harness deploys to Cloud Run. The central research question: with 2026-era models that already support native parallel tool-use, does explicit DAG planning still provide latency and cost advantages, and on which task patterns?

## 1. Stack

- **Language:** Python 3.11+
- **Primary LLM:** Gemini 2.5 Flash via `google-genai` SDK (Google AI Studio Tier 1; ~1000 RPM, paid)
- **Secondary LLM (Weekend 3):** Claude Sonnet 4.6 via `anthropic` SDK, for cross-provider validation
- **Agent frameworks:** custom (from-scratch), LangGraph, Google ADK — all three call the same shared DAG executor
- **Concurrency:** `asyncio`
- **Observability:** OpenTelemetry → Langfuse (LLM tracing) + Cloud Trace (distributed tracing)
- **State persistence:** SQLite locally, Firestore in GCP deploy
- **Deployment:** Cloud Run + Vertex AI
- **Reference:** LLMCompiler paper (arXiv:2312.04511, ICML 2024)

## 2. Repository structure (final state)

```
llm-agent-dag-planner/
├── README.md
├── SPEC.md
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile                       # weekend 3
├── cloudbuild.yaml                  # weekend 3
├── src/
│   ├── __init__.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                  # LLMProvider abstract base
│   │   ├── gemini.py                # Primary provider (Google AI Studio)
│   │   └── claude.py                # Weekend 3 — second provider
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── wikipedia.py
│   │   ├── github.py                # weekend 2
│   │   └── bfcl_tools.py            # weekend 2
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── react.py
│   │   ├── native_parallel.py
│   │   ├── dag_planner.py           # the shared DAG core
│   │   ├── dag_planner_langgraph.py # weekend 2 — frontend on shared core
│   │   └── dag_planner_adk.py       # weekend 2 — frontend on shared core
│   ├── core/
│   │   ├── __init__.py
│   │   ├── dag.py
│   │   └── state.py
│   ├── metrics.py
│   ├── tracing.py                   # weekend 3
│   ├── judge.py
│   └── run_eval.py
├── benchmarks/
│   ├── hotpotqa/{load.py, tasks.json}
│   ├── bfcl/{load.py, tasks.json}
│   └── github/{tasks.json}
├── results/{results.json, results.md, plots/}
├── notebooks/
│   └── analyze_results.ipynb
├── scripts/
│   ├── verify_step1.py
│   ├── ...
│   └── plot_results.py
└── deploy/
    └── cloud_run_eval.py
```

## 3. THREE-WEEKEND BUILD PLAN

**WEEKEND 1: Core technical contribution (Steps 1-8)**
**WEEKEND 2: Coverage expansion (Steps 9-13)**
**WEEKEND 3: Production hardening (Steps 14-19)**

**After each step, STOP and wait for user verification before proceeding to the next step.**

---

## WEEKEND 1 — Core (8 steps)

### Step 1: `src/llm/base.py` + `src/llm/gemini.py` — instrumented Gemini provider

`requirements.txt` should include `google-genai` (not the deprecated `google-generativeai`).

Define `LLMProvider` ABC in `src/llm/base.py` with one async method:
```python
async def call(
    messages: list[dict],
    tools: list[ToolDef] | None = None,
    system: str | None = None,
    force_single_tool_call: bool = False,
    max_tokens: int = 4096,
) -> tuple[Response, CallMetrics]
```

`CallMetrics` dataclass: `latency_seconds`, `input_tokens`, `output_tokens`, `cost_usd`, `n_tool_calls`, `stop_reason`.

Implement `GeminiProvider(LLMProvider)` in `src/llm/gemini.py`:

- Use `from google import genai` and `from google.genai import types`
- Async client: `client = genai.Client(api_key=os.environ['GEMINI_API_KEY']).aio`
- Call: `await client.models.generate_content(model="gemini-2.5-flash", contents=..., config=types.GenerateContentConfig(tools=tools, system_instruction=system))`
- For tools: convert your `ToolDef` to `types.Tool(function_declarations=[...])`. Each function declaration takes `{"name", "description", "parameters"}` where parameters is a JSON schema dict.
- Parse the response:
  - Find function_call parts: `[part for part in response.candidates[0].content.parts if part.function_call]`
  - `n_tool_calls = len(function_calls)`
  - `stop_reason` ← `response.candidates[0].finish_reason.name` (e.g. "STOP", "MAX_TOKENS", or use "tool_use" if function_calls present)
  - Token usage: `response.usage_metadata.prompt_token_count` and `response.usage_metadata.candidates_token_count`
- Pricing constants at top of file:
  ```python
  # Gemini 2.5 Flash — Google AI Studio paid-tier pricing as of May 2026
  # User is on FREE tier; these are for cost-reporting in benchmarks
  INPUT_COST_PER_MTOK = 0.30
  OUTPUT_COST_PER_MTOK = 2.50
  ```
- Use `time.perf_counter()` for latency.

**Important: there is no `disable_parallel_tool_use` flag in Gemini.** The provider just returns whatever it returns. The *strategies* (Step 3 and Step 7) will handle whether to honor or discard extra parallel calls.

Verification script `scripts/verify_step1.py`: two calls (one without tools, one with a mock `get_weather` tool). Print both `CallMetrics`. Use a sequential prompt for call 1 ("What is 2+2? Reply with just the number.") and a tool-eliciting prompt for call 2 ("What's the weather in San Francisco?").

### Step 2: `src/tools/base.py` + `src/tools/wikipedia.py`

(Same as before.)

`Tool` dataclass: `name`, `description`, `input_schema` (JSON schema dict), `execute` (async callable).

Wikipedia tools:
- `wikipedia_search(query: str) -> list[str]` — top-5 article titles via `https://en.wikipedia.org/w/api.php`
- `wikipedia_fetch(title: str) -> str` — first 500 words

Use `httpx.AsyncClient`. Set User-Agent `"llm-agent-dag-planner/0.1 (rohanc@gmail.com)"`.

### Step 3: `src/strategies/react.py`

Standard ReAct loop, **forced sequential by post-hoc filtering**:

```python
response, metrics = await llm.call(messages, tools=tool_defs, force_single_tool_call=True)
# Gemini may return multiple function_calls. Honor only the first for ReAct semantics.
function_calls = extract_function_calls(response)
if function_calls:
    first_call = function_calls[0]
    # Execute only the first, discard others
    result = await execute_tool(first_call)
    append result to messages
    # (Discarded calls are logged but not executed.)
```

This matches the original ReAct paper's "one action per step" semantics. **Document this clearly in the README** so anyone reading the project understands the methodology choice (forced by Gemini API surface, not the strategy's design).

The `force_single_tool_call` flag is passed to the provider so it can add a system-prompt hint ("Call exactly one function per turn, then wait for results before continuing"), and the strategy *also* discards extras post-hoc. Belt and suspenders.

### Step 4: `benchmarks/hotpotqa/load.py` + sample 30 tasks

Download HotpotQA dev set from `https://hotpotqa.github.io/`. Filter for `"type": "bridge"`. Sample 30 deterministically (seed=42). Save `tasks.json`. Gitignore the raw download; commit the sampled `tasks.json`.

### Step 5: `src/judge.py`

`async def judge_answer(question, gold, predicted) -> {"correct": bool, "rationale": str}`. Uses `GeminiProvider.call` (no tools) with a system prompt for semantic equivalence on short spans.

### Step 6: `src/run_eval.py` — first end-to-end

CLI: `python -m src.run_eval --strategy react --benchmark hotpotqa --n 30`.

Output (saved to `results/results.json`):
```
Strategy: react
Benchmark: hotpotqa  
Accuracy: X/30 (Y%)
Latency p50/p95/mean
Tokens (input/output)
Cost mean / total
LLM calls per task
Tool calls per task
```

**Milestone: working eval pipeline.**

### Step 7: `src/strategies/native_parallel.py`

Standard ReAct-like loop but **honor all function_calls returned in each turn**. Execute concurrently with `asyncio.gather`.

This is the natural Gemini behavior — no special flag needed. The contrast with Step 3 (which discards extras) makes the experimental design clean.

### Step 8: `src/core/dag.py` + `src/strategies/dag_planner.py` — the contribution

**`src/core/dag.py`:**
- `Task` dataclass: `id: int`, `tool: str`, `args: dict`, `depends_on: list[int]`
- `DAG` dataclass: `tasks: list[Task]`
- `topological_levels(dag) -> list[list[Task]]` — Kahn's algorithm
- `substitute_placeholders(args, prior_outputs) -> dict` — handles `"$task_<id>"` and `"$task_<id>.field"`
- Unit tests for both

**`src/strategies/dag_planner.py`:**

Phase A — planning. Single LLM call with a special `submit_plan` function declaration:

```python
submit_plan = types.FunctionDeclaration(
    name="submit_plan",
    description="Submit the complete execution plan as a DAG of tasks.",
    parameters={
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
        },
        "required": ["tasks"]
    }
)
```

In the planner's system prompt, describe the actual tools (Wikipedia, GitHub, etc.) but only expose `submit_plan` as a callable function. Use Gemini's `tool_config` with `function_calling_config={"mode": "ANY", "allowed_function_names": ["submit_plan"]}` to force the model to call `submit_plan` exactly.

Phase B — execute the DAG (using `core/dag.py`). Substitute `"$task_<id>"` placeholders with prior outputs. Each topological level runs concurrently with `asyncio.gather`.

Final synthesis — one more LLM call (no tools) that gets the question + task outputs and produces the answer.

Total LLM calls: 2.

**Weekend 1 deliverable:** three strategies, HotpotQA benchmark, full metrics.

---

## WEEKEND 2 — Coverage (5 steps)

### Step 9: GitHub tools + custom benchmark

`src/tools/github.py` — async tools against `https://api.github.com`. With a `GITHUB_TOKEN` you get 5000 req/hr.

Tools: `github_get_repo`, `github_get_latest_release`, `github_get_top_contributors`, `github_get_open_issues_count`, `github_search_repos`.

`benchmarks/github/tasks.json` — 25 hand-crafted tasks:
- ~10 embarrassingly parallel
- ~10 mixed (sequential then parallel)
- ~5 control / sequential

Schema: `{"id", "question", "answer", "answer_type": "list|count|name", "expected_parallel_count": N}`.

Run all 3 strategies on GitHub benchmark.

### Step 10: BFCL parallel subset

Clone `https://github.com/ShishirPatil/gorilla`. Pull the `parallel_function` category from `berkeley-function-call-leaderboard/data/`.

Eval mode for BFCL: function definitions become no-op stubs that log what was called. Compare logged set to expected (AST-equivalent). Accuracy = "did the strategy emit the right tool calls?"

### Step 11: `src/strategies/dag_planner_langgraph.py`

LangGraph re-implementation. Use `StateGraph` with a TypedDict state (`messages`, `dag`, `outputs`, `final_answer`).

Nodes: `planner` → `executor` (calls `core/dag.py`) → `synthesizer`.

The LangGraph version is a ~80-line frontend; **the DAG executor is the same shared function from `core/dag.py`** — not re-implemented. Use LangGraph's checkpointing for state — note this in the README as LangGraph's value-add.

### Step 12: `src/strategies/dag_planner_adk.py`

Google ADK re-implementation. ADK has `SequentialAgent` and `ParallelAgent` primitives — perfect fit.

- Planning step: `LlmAgent` with the `submit_plan` tool
- Execution: dynamically construct `SequentialAgent([ParallelAgent(level_1_tasks), ParallelAgent(level_2_tasks), ...])`
- Synthesis: another `LlmAgent`

Same approach as Step 11: shared `core/dag.py`, this file is the ADK frontend. ADK uses Gemini natively, so this is also the place where Vertex AI integration starts.

### Step 13: All-up eval + `notebooks/analyze_results.ipynb`

Matrix: 5 strategies × 3 benchmarks = 15 cells. Save to `results/results.json`.

Notebook produces:
- Main results table
- Scatter plot: latency vs accuracy
- Bar chart: latency speedup over ReAct per benchmark
- Cross-framework consistency table (custom / LangGraph / ADK)
- Breakdown on GitHub: parallel-friendly vs sequential tasks

---

## WEEKEND 3 — Production (6 steps)

### Step 14: `src/tracing.py` — OpenTelemetry

Two exporters:
1. **OTLP → Langfuse** (LLM-specific spans with prompt/response/cost)
2. **Cloud Trace** (general distributed tracing)

Use OpenTelemetry GenAI semantic conventions (`gen_ai.system`, `gen_ai.usage.input_tokens`, etc.).

Wrap every LLM call and every tool call in a span with attributes for strategy/benchmark/task_id.

Verify: one HotpotQA task with tracing on; screenshot the trace in Langfuse and Cloud Trace for the README.

### Step 15: `src/core/state.py` — state persistence

Persist DAG intermediate outputs to:
- SQLite locally
- Firestore in GCP deploy (env-toggled)

Schema:
```
runs(run_id, strategy, benchmark, task_id, started_at, finished_at, status)
task_outputs(run_id, task_node_id, output_json, completed_at)
```

Enables checkpoint/resume.

### Step 16: `src/llm/claude.py` — Claude as second provider

Implement `ClaudeProvider(LLMProvider)` using `anthropic` SDK. Same interface as `GeminiProvider`.

- Model: `claude-sonnet-4-6`
- `force_single_tool_call=True` → set `tool_choice={"type": "auto", "disable_parallel_tool_use": True}` (Claude *does* support this flag natively, unlike Gemini)
- Pricing: `$3.00/MTok input, $15.00/MTok output`

CLI flag: `--llm-provider {gemini,claude}`.

Run a cross-provider validation: HotpotQA across all 5 strategies on Claude. This costs ~$1-2 in API credits. The headline finding becomes "Gemini-first results validated against Claude — observed effects are consistent across providers."

### Step 17: Dockerfile + Cloud Run deploy

`Dockerfile` (python:3.11-slim), `cloudbuild.yaml` for Artifact Registry push.

Deploy:
```bash
gcloud run deploy llm-agent-dag-planner \
  --image us-central1-docker.pkg.dev/PROJECT/repo/llm-agent-dag-planner \
  --region us-central1 \
  --set-secrets GEMINI_API_KEY=gemini-key:latest,ANTHROPIC_API_KEY=anthropic-key:latest,LANGFUSE_PUBLIC_KEY=lf-pub:latest,LANGFUSE_SECRET_KEY=lf-sec:latest
```

Service runs the eval, writes results to a Cloud Storage bucket. Document the commands in README.

### Step 18: Architecture diagram + cleanup

Mermaid diagram showing Cloud Run, Gemini (AI Studio + Vertex), Anthropic, Cloud Storage, Firestore, Langfuse, Cloud Trace.

Pinned deps, type hints, docstrings, README polish.

### Step 19: README + final polish

README sections:
1. TL;DR — headline numbers
2. Motivation — cite LLMCompiler, note 2026 context
3. Methods — five strategies, Mermaid diagram, **note the ReAct sequentialization caveat**
4. Benchmarks — three benchmarks
5. Results — main table, scatter, cross-framework consistency, cross-provider validation
6. Findings — 3-4 concrete bullets
7. Architecture — production diagram
8. Observability — Langfuse + Cloud Trace screenshots
9. Reproducibility — local + cloud commands
10. Limitations
11. References

Optional: 2-min Loom video walk-through.

---

## 4. Resume bullet target (final)

> Re-implemented LLMCompiler (ICML 2024) DAG-based parallel function calling using Gemini 2.5 Flash and Claude Sonnet 4.6, with three framework variants (from-scratch, LangGraph, Google ADK); benchmarked against ReAct and native parallel tool-use on HotpotQA, BFCL v3, and a custom GitHub-API benchmark — measured [X.Y]x latency speedup and [Z]% cost reduction at parity accuracy. Deployed on Cloud Run with OpenTelemetry tracing to Langfuse and Cloud Trace.

## 5. Anti-goals

- LangChain (LangGraph alone is sufficient)
- CrewAI
- Self-hosted Langfuse — use cloud free tier
- Training/fine-tuning/LoRA
- K8s/GKE — Cloud Run is enough
- Vertex AI Gemini in Weekend 1 — AI Studio free tier first; move to Vertex AI in Weekend 3 deployment

## 6. Notes for Claude Code (apply throughout)

- `asyncio` throughout, never threading
- `httpx` async for HTTP, never `requests`
- `python-dotenv` for `.env`
- Pin versions in `requirements.txt`
- Unit-test the DAG topological sort and the placeholder substitution
- **After each numbered step, STOP and wait for user verification.**
- When the user says "proceed with Step N", read this SPEC.md section for Step N first.
- The methodology caveat about ReAct discarding extra parallel calls under Gemini must be documented in the README.

## 7. References

- LLMCompiler: arXiv:2312.04511
- HotpotQA: arXiv:1809.09600
- BFCL: github.com/ShishirPatil/gorilla
- ReAct: arXiv:2210.03629
- LangGraph: github.com/langchain-ai/langgraph
- Google ADK: github.com/google/adk-python, adk.dev
- Langfuse: langfuse.com
- google-genai SDK: googleapis.github.io/python-genai
- OpenTelemetry GenAI: opentelemetry.io/docs/specs/semconv/gen-ai/
