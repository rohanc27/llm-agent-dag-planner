from __future__ import annotations

"""LLMCompiler-style DAG planner — the headline contribution.

Three phases per task:

  1. **Plan** — single LLM call. Gemini is forced (via
     ``forced_function_name="submit_plan"``) to emit one ``submit_plan``
     function call whose ``tasks`` argument is the full execution DAG. The
     planner sees real tool descriptions in its system prompt but cannot
     invoke them — only ``submit_plan``. This cleanly separates planning
     from execution.

  2. **Execute** — no LLM. We toposort the DAG with
     :func:`src.core.dag.topological_levels` and fire each level's tasks
     concurrently via :func:`asyncio.gather`. Placeholders like
     ``"$task_2"`` and ``"$task_2.0"`` are substituted with prior outputs
     just before each tool call. Per-task failures are captured as
     ``{"error": "..."}`` so dependent tasks still see *something* — a
     single bad lookup never aborts the whole DAG.

  3. **Synthesize** — single LLM call, no tools, no ``tool_config``. The
     prompt is the original question plus a formatted summary of every
     task's output. We reuse :data:`src.strategies.react.REACT_SYSTEM_PROMPT`
     so accuracy comparisons against ReAct / native_parallel are fair.

Total LLM calls per task: **2** (regardless of plan size). Total
wall-clock ≈ ``latency(plan) + max(level_latencies) + latency(synth)``.

See SPEC.md § 3 Step 8.
"""

import asyncio
import json
import logging
import re
import time
from json import JSONDecodeError
from typing import Any, Optional

from src.core.dag import (
    DAG,
    Task,
    substitute_placeholders,
    topological_levels,
)
from src.llm.base import LLMProvider
from src.llm.gemini import extract_function_calls, extract_text
from src.metrics import AggregateMetrics
from src.strategies.react import REACT_SYSTEM_PROMPT
from src.tools.base import Tool

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Planner-facing ``submit_plan`` function declaration.
# -----------------------------------------------------------------------------
# SPEC.md § 3 Step 8 prescribes ``args`` as ``{"type": "object"}``. In
# practice the google-genai SDK strips properties-less object schemas in
# its native ``Schema`` conversion, and Gemini consistently emits ``{}``
# for the field. We work around this by declaring ``args`` as a JSON-
# encoded STRING — the model fills it happily, and we ``json.loads`` it
# in ``_build_dag_from_plan``. The semantic contract (an args object that
# matches the tool's input schema) is unchanged.
SUBMIT_PLAN_TOOL_DEF: dict[str, Any] = {
    "name": "submit_plan",
    "description": (
        "Submit the complete execution plan as a DAG of tasks. Tasks with "
        "no dependencies will run in parallel; tasks with dependencies will "
        "run after their dependencies complete. Use \"$task_<id>\" "
        "placeholders inside args to reference outputs of earlier tasks "
        "(e.g. \"$task_0\" for the full output of task 0, or "
        "\"$task_0.0\" for the first element if task 0 returned a list)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "tool": {"type": "string"},
                        "args": {
                            "type": "string",
                            "description": (
                                "JSON-encoded object of keyword arguments "
                                "for the tool, matching the tool's input "
                                "schema field names. Example: "
                                '\'{"query": "Eiffel Tower"}\' or '
                                '\'{"title": "$task_0.0"}\'.'
                            ),
                        },
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                    "required": ["id", "tool", "args", "depends_on"],
                },
            },
        },
        "required": ["tasks"],
    },
}


_PLACEHOLDER_SHAPE_RE = re.compile(r"^\$task_(\d+)(?:\.(.+))?$")


# -----------------------------------------------------------------------------
# Planner-prompt construction
# -----------------------------------------------------------------------------
def _format_tools_for_planner(tools: list[Tool]) -> str:
    """Render the real tools as a textual catalogue for the planner system
    prompt — the model cannot call them directly, only refer to them by
    name inside the submitted plan."""
    lines = ["Available tools you can plan with (callable indirectly via submit_plan):"]
    for t in tools:
        props = t.input_schema.get("properties", {}) if isinstance(t.input_schema, dict) else {}
        required = set(t.input_schema.get("required", [])) if isinstance(t.input_schema, dict) else set()
        params = []
        for k, v in props.items():
            type_str = v.get("type", "?") if isinstance(v, dict) else "?"
            mark = "" if k in required else "?"
            params.append(f"{k}{mark}: {type_str}")
        params_str = ", ".join(params) if params else ""
        lines.append(f"  - {t.name}({params_str}): {t.description}")
    return "\n".join(lines)


_PLANNER_INSTRUCTIONS: str = (
    "Output the complete execution plan as a DAG of tasks. Each task has:\n"
    "  - id (integer, starting at 0, unique)\n"
    "  - tool (the name of one of the available tools)\n"
    "  - args (a JSON-ENCODED STRING of the keyword arguments — see below)\n"
    "  - depends_on (a list of prior task ids; empty list when independent)\n"
    "\n"
    "CRITICAL: ``args`` must be a JSON-encoded STRING (not an object) whose "
    "content is the concrete keyword arguments the tool expects (matching "
    "its input schema field names). Never emit an empty object string — "
    "that will fail with a missing argument error.\n"
    "\n"
    "Placeholders: use \"$task_<id>\" as the entire value of an arg field to "
    "reference the output of an earlier task. Use \"$task_<id>.<path>\" to "
    "pluck a field / list index inside the args object:\n"
    "  - {\"title\": \"$task_0\"} — pass task 0's full output\n"
    "  - {\"title\": \"$task_0.0\"} — first element when task 0 returned a list\n"
    "  - {\"title\": \"$task_0.results.title\"} — dotted field path\n"
    "A placeholder must be the ENTIRE arg value (no mid-string interpolation).\n"
    "\n"
    "Worked example (for the question 'Who composed the music for the film "
    "directed by Christopher Nolan in 2010?'):\n"
    "  {\n"
    "    \"tasks\": [\n"
    "      {\"id\": 0, \"tool\": \"wikipedia_search\", \"args\": \"{\\\"query\\\": \\\"Christopher Nolan filmography 2010\\\"}\", \"depends_on\": []},\n"
    "      {\"id\": 1, \"tool\": \"wikipedia_fetch\", \"args\": \"{\\\"title\\\": \\\"$task_0.0\\\"}\", \"depends_on\": [0]},\n"
    "      {\"id\": 2, \"tool\": \"wikipedia_search\", \"args\": \"{\\\"query\\\": \\\"Inception 2010 film composer\\\"}\", \"depends_on\": [1]},\n"
    "      {\"id\": 3, \"tool\": \"wikipedia_fetch\", \"args\": \"{\\\"title\\\": \\\"$task_2.0\\\"}\", \"depends_on\": [2]}\n"
    "    ]\n"
    "  }\n"
    "Note: every ``args`` value is a JSON STRING; the object inside is the "
    "tool's keyword arguments. Placeholders are used only where chaining is "
    "genuinely needed.\n"
    "\n"
    "Plan greedily for parallelism: tasks that don't actually depend on each "
    "other should have empty depends_on lists so they execute concurrently. "
    "Only add a dependency when the result of one task is genuinely needed "
    "to build the args of another.\n"
    "\n"
    "PLACEHOLDER SYNTAX (strict):\n"
    "A placeholder must be EXACTLY one of:\n"
    "  - \"$task_<id>\"           — the entire output of an earlier task\n"
    "  - \"$task_<id>.<path>\"    — a field / list-index path on that output\n"
    "and it must be the ENTIRE value of the arg field. You CANNOT embed extra "
    "words, transformations, or descriptions inside or alongside it.\n"
    "  VALID:    \"$task_1\", \"$task_0.0\", \"$task_3.title\"\n"
    "  INVALID:  \"$task_1 record label subsidiary\"   (extra words after)\n"
    "  INVALID:  \"$task_1.subsidiary parent company\" (extra words after)\n"
    "  INVALID:  \"the article about $task_1\"          (embedded mid-string)\n"
    "If you need to use a task's output as part of a more complex query for "
    "a later task, pass the placeholder as the whole arg value to a search/"
    "fetch tool and let that tool surface what you need. Do not try to "
    "interpolate placeholders inside larger strings.\n"
    "\n"
    "MULTI-HOP PLANNING:\n"
    "For questions whose answer is a property of an entity that must first "
    "be identified through another entity (e.g. \"the X of the Y of Z\"), "
    "plan at least two search+fetch pairs at different levels of the DAG. "
    "Be speculative: include extra fetch tasks at higher topological levels "
    "rather than fewer — unused tasks are cheap, missing tasks make the "
    "question unanswerable.\n"
    "\n"
    "Example plan structure for a 3-hop question:\n"
    "  Level 0: search for entity Z\n"
    "  Level 1: fetch the article identified in level 0 (placeholder $task_0.0)\n"
    "  Level 2: search for entity Y mentioned in Z's article\n"
    "  Level 3: fetch the article identified in level 2 (placeholder $task_2.0)\n"
)


def _planner_system_prompt(tools: list[Tool]) -> str:
    return f"{_format_tools_for_planner(tools)}\n\n{_PLANNER_INSTRUCTIONS}"


# -----------------------------------------------------------------------------
# Plan validation
# -----------------------------------------------------------------------------
class PlanValidationError(ValueError):
    """Raised when the planner's output is structurally unusable."""


def _validate_placeholders(tasks: list[Task], all_ids: set[int]) -> None:
    """Walk every arg looking for ``$task_*`` strings and check shape + refs."""

    def walk(value: Any, owner_id: int) -> None:
        if isinstance(value, str) and value.startswith("$task_"):
            m = _PLACEHOLDER_SHAPE_RE.match(value)
            if m is None:
                raise PlanValidationError(
                    f"Task {owner_id}: malformed placeholder {value!r}"
                )
            ref = int(m.group(1))
            if ref not in all_ids:
                raise PlanValidationError(
                    f"Task {owner_id}: placeholder $task_{ref} references "
                    f"missing task id"
                )
        elif isinstance(value, dict):
            for v in value.values():
                walk(v, owner_id)
        elif isinstance(value, list):
            for v in value:
                walk(v, owner_id)

    for t in tasks:
        walk(t.args, t.id)


def _build_dag_from_plan(
    plan_args: dict[str, Any],
    tools_by_name: dict[str, Tool],
) -> DAG:
    """Convert the planner's ``submit_plan`` args into a validated :class:`DAG`."""
    raw_tasks = plan_args.get("tasks") if isinstance(plan_args, dict) else None
    if not isinstance(raw_tasks, list):
        raise PlanValidationError(
            f"submit_plan args missing 'tasks' list; got {type(raw_tasks).__name__}"
        )

    tasks: list[Task] = []
    for i, raw in enumerate(raw_tasks):
        if not isinstance(raw, dict):
            raise PlanValidationError(f"Task at index {i} is not an object")
        try:
            tid = int(raw["id"])
            tool_name = str(raw["tool"])
            args = raw["args"]
            depends_on_raw = raw["depends_on"]
        except (KeyError, ValueError, TypeError) as exc:
            raise PlanValidationError(
                f"Task at index {i} has malformed structure: {exc}"
            ) from exc

        # ``args`` is normally a JSON-encoded string (per the workaround
        # described on SUBMIT_PLAN_TOOL_DEF), but we also accept a raw dict
        # — both shapes round-trip to the same execution semantics.
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except JSONDecodeError as exc:
                raise PlanValidationError(
                    f"Task {tid} args is not valid JSON: {exc}"
                ) from exc
        if not isinstance(args, dict):
            raise PlanValidationError(
                f"Task {tid} args must be a JSON object (or a JSON-string "
                f"encoding one); got {type(args).__name__}"
            )
        if tool_name not in tools_by_name:
            raise PlanValidationError(
                f"Task {tid} references unknown tool {tool_name!r}; "
                f"available: {sorted(tools_by_name)}"
            )
        try:
            depends_on = [int(d) for d in depends_on_raw]
        except (TypeError, ValueError) as exc:
            raise PlanValidationError(
                f"Task {tid} depends_on must be a list of integers: {exc}"
            ) from exc

        tasks.append(
            Task(id=tid, tool=tool_name, args=args, depends_on=depends_on)
        )

    all_ids = {t.id for t in tasks}
    _validate_placeholders(tasks, all_ids)

    dag = DAG(tasks=tasks)
    # topological_levels surfaces cycles, duplicate ids, missing deps. We
    # invoke it eagerly so validation errors land here in plan-building.
    topological_levels(dag)
    return dag


# -----------------------------------------------------------------------------
# Execution
# -----------------------------------------------------------------------------
async def _run_single_task(
    task: Task,
    tools_by_name: dict[str, Tool],
    outputs: dict[int, Any],
    metrics: AggregateMetrics,
    task_debug: Optional[dict[str, Any]] = None,
) -> tuple[int, Any]:
    """Execute one task. ``task_debug`` is an optional per-task sink that,
    if provided, is populated with ``task_id``/``tool``/``args_raw``/
    ``depends_on``/``args_substituted``/``output``. Pure addition for the
    diagnostic script — does not affect execution behavior."""
    if task_debug is not None:
        task_debug["task_id"] = task.id
        task_debug["tool"] = task.tool
        task_debug["args_raw"] = task.args
        task_debug["depends_on"] = list(task.depends_on)
        task_debug["args_substituted"] = None
        task_debug["output"] = None

    tool = tools_by_name.get(task.tool)
    if tool is None:
        out: Any = {"error": f"unknown tool {task.tool!r}"}
        if task_debug is not None:
            task_debug["output"] = out
        return task.id, out

    try:
        resolved_args = substitute_placeholders(task.args, outputs)
    except ValueError as exc:
        out = {"error": f"placeholder substitution failed: {exc}"}
        if task_debug is not None:
            task_debug["output"] = out
        return task.id, out

    if not isinstance(resolved_args, dict):
        out = {
            "error": (
                f"resolved args for task {task.id} are not an object: "
                f"{type(resolved_args).__name__}"
            )
        }
        if task_debug is not None:
            task_debug["args_substituted"] = resolved_args
            task_debug["output"] = out
        return task.id, out

    if task_debug is not None:
        task_debug["args_substituted"] = resolved_args

    # We're about to actually hit the external service — count it. Tasks
    # that bail out above (unknown tool, placeholder failure, malformed
    # args) never reach Wikipedia/GitHub/etc. and so don't count as
    # "executed". This is the more honest definition per SPEC §8 fix.
    metrics.n_tools_executed += 1
    try:
        result = await tool.execute(**resolved_args)
    except Exception as exc:  # noqa: BLE001 — feed errors forward
        out = {"error": f"tool {task.tool} raised: {exc}"}
        if task_debug is not None:
            task_debug["output"] = out
        return task.id, out

    if task_debug is not None:
        task_debug["output"] = result

    return task.id, result


async def _execute_dag(
    dag: DAG,
    tools_by_name: dict[str, Tool],
    levels: list[list[Task]],
    metrics: AggregateMetrics,
    debug_levels: Optional[list[dict[str, Any]]] = None,
) -> dict[int, Any]:
    """Execute ``dag`` level-by-level. Returns ``{task_id: output}``.

    Within each level, tasks are scheduled with :func:`asyncio.gather`.
    Output dict is updated after each level so subsequent levels can
    resolve placeholders. ``metrics.n_tools_executed`` is incremented
    once per task that actually reaches its ``tool.execute()`` call.

    ``debug_levels``: optional list to which one ``{"level", "tasks": [...]}``
    entry is appended per level. Pure addition for the diagnostic script.
    """
    outputs: dict[int, Any] = {}
    for level_idx, level in enumerate(levels):
        logger.info(
            "dag_planner level %d: %d task(s) — %s",
            level_idx,
            len(level),
            [(t.id, t.tool) for t in level],
        )
        task_debugs: list[Optional[dict[str, Any]]]
        if debug_levels is not None:
            task_debugs = [dict() for _ in level]
        else:
            task_debugs = [None] * len(level)
        level_results = await asyncio.gather(
            *(
                _run_single_task(
                    t, tools_by_name, outputs, metrics, task_debug=td
                )
                for t, td in zip(level, task_debugs)
            )
        )
        if debug_levels is not None:
            debug_levels.append(
                {"level": level_idx, "tasks": [td for td in task_debugs]}
            )
        for tid, output in level_results:
            outputs[tid] = output
    return outputs


# -----------------------------------------------------------------------------
# Synthesis
# -----------------------------------------------------------------------------
_SYNTH_OUTPUT_TRUNCATE: int = 2000


def _format_outputs_for_synthesis(
    dag: DAG, outputs: dict[int, Any]
) -> str:
    """Render task outputs as a numbered, lightly-truncated bullet list."""
    lines: list[str] = []
    for task in dag.tasks:
        raw = outputs.get(task.id, "<not executed>")
        if isinstance(raw, str):
            body = raw
        else:
            try:
                body = json.dumps(raw, ensure_ascii=False)
            except (TypeError, ValueError):
                body = repr(raw)
        if len(body) > _SYNTH_OUTPUT_TRUNCATE:
            body = body[:_SYNTH_OUTPUT_TRUNCATE] + " … (truncated)"
        lines.append(f"Task {task.id} ({task.tool}): {body}")
    return "\n".join(lines)


async def _synthesize(
    question: str,
    dag: DAG,
    outputs: dict[int, Any],
    llm: LLMProvider,
    metrics: AggregateMetrics,
    debug: Optional[dict[str, Any]] = None,
) -> str:
    user_msg = (
        f"Question: {question}\n\n"
        f"Tool execution results:\n"
        f"{_format_outputs_for_synthesis(dag, outputs)}\n\n"
        f"Using only the results above, give a concise final answer in plain text."
    )
    if debug is not None:
        debug["synth_system_prompt"] = REACT_SYSTEM_PROMPT
        debug["synth_user_prompt"] = user_msg
    response, call_metrics = await llm.call(
        messages=[{"role": "user", "content": user_msg}],
        system=REACT_SYSTEM_PROMPT,
    )
    metrics.add_call(call_metrics, add_to_wall_clock=False)
    text = extract_text(response)
    if debug is not None:
        debug["synth_response"] = text
    return text


# -----------------------------------------------------------------------------
# Top-level entrypoint
# -----------------------------------------------------------------------------
_EMPTY_RESULT_PREFIX: str = "DAG_PLANNER_EMPTY_RESULT"


async def run_dag_planner(
    question: str,
    tools: list[Tool],
    llm: LLMProvider,
    trace: Optional[dict[str, Any]] = None,
    debug: Optional[dict[str, Any]] = None,
) -> tuple[str, AggregateMetrics]:
    """Run plan → execute → synthesize on one question.

    Parameters
    ----------
    question, tools, llm:
        As for the other strategies.
    trace:
        Optional dict that, if provided, is populated with diagnostic
        information (``plan_raw``, ``dag``, ``levels``, ``outputs``).
        Used by :mod:`scripts.verify_step8`; ignored by the eval harness.

    Returns
    -------
    tuple
        ``(final_answer, AggregateMetrics)``. ``total_wall_clock_seconds``
        is the externally-measured wall clock across all three phases.

    Empty-answer contract
    ---------------------
    This function NEVER returns ``("", metrics)``. If the planner emits a
    structurally invalid plan, we catch :class:`PlanValidationError` and
    surface it as ``"DAG_PLANNER_EMPTY_RESULT: <reason>"`` so the metrics
    accumulated up to that point (e.g. the plan LLM call) survive into
    the eval row. Likewise if synthesis returns empty text. Unexpected
    exceptions (network, internal bugs) still propagate so they land in
    the eval harness's ``error`` field for debugging.
    """
    tools_by_name = {t.name: t for t in tools}
    metrics = AggregateMetrics()
    final_answer: str = ""
    dag_for_diag: Optional[DAG] = None
    outputs_for_diag: dict[int, Any] = {}

    planner_system_prompt = _planner_system_prompt(tools)

    if debug is not None:
        debug["planner_system_prompt"] = planner_system_prompt
        debug["planner_user_prompt"] = question
        debug["plan_raw"] = None
        debug["plan_validation"] = None
        debug["level_executions"] = []
        debug["synth_system_prompt"] = None
        debug["synth_user_prompt"] = None
        debug["synth_response"] = None

    wall_clock_start = time.perf_counter()
    try:
        try:
            # -- Phase 1: Plan -----------------------------------------------
            plan_response, plan_metrics = await llm.call(
                messages=[{"role": "user", "content": question}],
                tools=[SUBMIT_PLAN_TOOL_DEF],
                system=planner_system_prompt,
                forced_function_name="submit_plan",
            )
            metrics.add_call(plan_metrics, add_to_wall_clock=False)

            plan_calls = extract_function_calls(plan_response)
            if not plan_calls or plan_calls[0].name != "submit_plan":
                raise PlanValidationError(
                    "planner did not emit submit_plan; got: "
                    f"{[c.name for c in plan_calls] or '(text-only)'}"
                )

            plan_args = plan_calls[0].args
            if debug is not None:
                debug["plan_raw"] = plan_args

            dag = _build_dag_from_plan(plan_args, tools_by_name)
            if debug is not None:
                debug["plan_validation"] = "ok"
            dag_for_diag = dag
            levels = topological_levels(dag)

            if trace is not None:
                trace["plan_raw"] = plan_args
                trace["dag"] = dag
                trace["levels"] = levels

            # -- Phase 2: Execute --------------------------------------------
            outputs = await _execute_dag(
                dag,
                tools_by_name,
                levels,
                metrics,
                debug_levels=(
                    debug["level_executions"] if debug is not None else None
                ),
            )
            outputs_for_diag = outputs
            if trace is not None:
                trace["outputs"] = outputs

            # -- Phase 3: Synthesize -----------------------------------------
            final_answer = await _synthesize(
                question, dag, outputs, llm, metrics, debug=debug
            )
            if trace is not None:
                trace["final_answer"] = final_answer
        except PlanValidationError as exc:
            reason = f"plan validation failed — {exc}"
            logger.warning("dag_planner: %s", reason)
            if debug is not None and (
                debug.get("plan_validation") is None
                or debug.get("plan_validation") == "ok"
            ):
                debug["plan_validation"] = f"error: {exc}"
            final_answer = f"{_EMPTY_RESULT_PREFIX}: {reason}"

        # Belt-and-suspenders: synth can legitimately return "" if Gemini
        # filtered or produced an empty response despite reaching it.
        if not final_answer or not final_answer.strip():
            if dag_for_diag is not None:
                n_err = sum(
                    1
                    for v in outputs_for_diag.values()
                    if isinstance(v, dict) and "error" in v
                )
                reason = (
                    f"synthesizer returned empty text "
                    f"(plan had {len(dag_for_diag.tasks)} task(s); "
                    f"{n_err} produced errors during execution)"
                )
            else:
                reason = "no answer produced (planning never completed)"
            logger.warning("dag_planner: %s", reason)
            final_answer = f"{_EMPTY_RESULT_PREFIX}: {reason}"
    finally:
        metrics.total_wall_clock_seconds = time.perf_counter() - wall_clock_start

    return final_answer, metrics
