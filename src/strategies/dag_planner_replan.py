from __future__ import annotations

"""DAG planner with adaptive replanning — Phase A contribution.

This is a thin shell around :mod:`src.strategies.dag_planner` that
addresses its biggest weakness on HotpotQA bridge: inability to recover
when an early retrieval returns the wrong article. The base strategy
plans up-front, executes, and synthesizes — if the search returns the
wrong page, there's no way back.

The replan loop adds one level of adaptivity *without* giving up the
"plan-then-execute" property:

  1. Initial planner call → DAG (LLM call 1).
  2. Execute the DAG level by level.
  3. After each level, check the configured ``trigger`` condition:

     * ``any_failure`` — at least one task in the level returned
       ``{"error": ...}``, ``None``, an empty string, or an empty list.
     * ``all_failure`` — every task in the level failed.
     * ``empty_synth`` — never fires here; checked AFTER synthesis on
       the final answer text (refusal-like phrases like "could not
       find," "no information," "unable to").

  4. If the trigger fires AND ``replans_used < max_replans`` —
     re-invoke the planner with the original question PLUS a textual
     summary of the prior attempts (which tasks were run, what each
     returned). Get a new DAG. Discard prior in-DAG outputs (approach
     A — clean re-execute) and run the new DAG from level 0. Increment
     ``metrics.n_replans``.

  5. Final synth call sees only the LATEST DAG's outputs.

  6. ``empty_synth`` only: after the final synth, if the answer looks
     like a refusal AND budget remains, trigger one more replan.

The strategy reuses ``submit_plan``, ``_planner_system_prompt``,
``_build_dag_from_plan``, ``_run_single_task``, ``_synthesize``, and
the empty-answer sentinel from :mod:`src.strategies.dag_planner` — only
the orchestration shell is new.

Total LLM calls per task: ``1 + replans_used + 1`` (initial plan +
replans + synth). With ``max_replans=2`` this caps at 4 calls; with
``max_replans=5`` it caps at 7. Compare to the base DAG planner at
exactly 2.
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

try:
    from typing import Literal
except ImportError:  # pragma: no cover — Python <3.8
    from typing_extensions import Literal  # type: ignore[no-redef]

from src.core.dag import DAG, topological_levels
from src.llm.base import LLMProvider
from src.llm.gemini import extract_function_calls
from src.metrics import AggregateMetrics
from src.strategies.dag_planner import (
    _EMPTY_RESULT_PREFIX,
    PlanValidationError,
    SUBMIT_PLAN_TOOL_DEF,
    _build_dag_from_plan,
    _planner_system_prompt,
    _run_single_task,
    _synthesize,
)
from src.tools.base import Tool

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Trigger logic
# -----------------------------------------------------------------------------
TriggerKind = Literal["any_failure", "all_failure", "empty_synth"]

# Short, mostly case-insensitive refusal markers used for the ``empty_synth``
# trigger. Conservative — we only fire when the synth is overtly disclaiming.
_REFUSAL_MARKERS: tuple[str, ...] = (
    "i cannot answer",
    "i can't answer",
    "i am unable to",
    "i'm unable to",
    "do not contain",
    "does not contain",
    "no information",
    "not enough information",
    "could not find",
    "couldn't find",
    "unable to determine",
    "is not ascertainable",
    "no answer can be provided",
    "no relevant information",
    "the provided information does not",
    "the provided results do not",
    "the provided text does not",
    "the provided search results do not",
)


def _looks_like_refusal(answer: str) -> bool:
    lower = (answer or "").lower()
    return any(marker in lower for marker in _REFUSAL_MARKERS)


def _is_failed_output(out: Any) -> bool:
    """A task output 'failed' if it surfaced an error or returned nothing."""
    if out is None:
        return True
    if isinstance(out, dict) and "error" in out:
        return True
    if isinstance(out, str) and not out.strip():
        return True
    if isinstance(out, list) and len(out) == 0:
        return True
    return False


def _level_trigger_fires(
    trigger: TriggerKind, level_tasks: list, outputs: dict
) -> bool:
    """Per-level trigger check. ``empty_synth`` never fires here."""
    if trigger == "empty_synth":
        return False
    level_outputs = [outputs.get(t.id) for t in level_tasks]
    if not level_outputs:
        return False
    fails = [_is_failed_output(o) for o in level_outputs]
    if trigger == "any_failure":
        return any(fails)
    if trigger == "all_failure":
        return all(fails)
    return False


# -----------------------------------------------------------------------------
# Planner-call helpers
# -----------------------------------------------------------------------------
def _summarize_output(out: Any, max_chars: int = 200) -> str:
    if out is None:
        return "(no output)"
    if isinstance(out, dict) and "error" in out:
        return f"ERROR: {out['error']}"
    if isinstance(out, str):
        return out if len(out) <= max_chars else out[:max_chars] + "…(truncated)"
    try:
        rendered = json.dumps(out, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        rendered = repr(out)
    return (
        rendered if len(rendered) <= max_chars else rendered[:max_chars] + "…(truncated)"
    )


def _replan_user_message(
    question: str, history: list[tuple[DAG, dict[int, Any]]]
) -> str:
    """Build the planner user prompt for a replan: question + prior history."""
    lines: list[str] = []
    for i, (prior_dag, prior_outputs) in enumerate(history, start=1):
        lines.append(f"--- Previous attempt #{i} ---")
        for task in prior_dag.tasks:
            out = prior_outputs.get(task.id, "<not executed>")
            lines.append(
                f"  Task {task.id}: {task.tool}({task.args}) → "
                f"{_summarize_output(out)}"
            )
        lines.append("")
    history_block = "\n".join(lines).rstrip()

    return (
        f"QUESTION: {question}\n\n"
        f"Previous execution attempts (one or more tasks failed or returned "
        f"empty results):\n\n"
        f"{history_block}\n\n"
        f"Submit a NEW execution plan. Pivot — try different search terms, "
        f"fetch different articles, or restructure the DAG so the failure has "
        f"a fallback. DO NOT repeat exact searches/fetches that previously "
        f"returned nothing useful. If a previous task DID succeed at a sub-step "
        f"of the question, you can build on that knowledge in your new plan."
    )


async def _do_plan_call(
    question: str,
    tools: list[Tool],
    llm: LLMProvider,
    metrics: AggregateMetrics,
    history: Optional[list[tuple[DAG, dict[int, Any]]]] = None,
) -> DAG:
    """One planner call. Raises :class:`PlanValidationError` on bad output."""
    user_msg = (
        _replan_user_message(question, history) if history else question
    )
    plan_response, plan_metrics = await llm.call(
        messages=[{"role": "user", "content": user_msg}],
        tools=[SUBMIT_PLAN_TOOL_DEF],
        system=_planner_system_prompt(tools),
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
    tools_by_name = {t.name: t for t in tools}
    return _build_dag_from_plan(plan_args, tools_by_name)


async def _execute_with_trigger(
    dag: DAG,
    tools_by_name: dict[str, Tool],
    metrics: AggregateMetrics,
    trigger: TriggerKind,
) -> tuple[dict[int, Any], Optional[int]]:
    """Execute the DAG level by level. Bail out if a level-trigger fires.

    Returns ``(outputs, level_idx_where_trigger_fired_or_None)``.
    """
    outputs: dict[int, Any] = {}
    levels = topological_levels(dag)
    for level_idx, level in enumerate(levels):
        logger.info(
            "dag_planner_replan level %d: %d task(s) — %s",
            level_idx,
            len(level),
            [(t.id, t.tool) for t in level],
        )
        level_results = await asyncio.gather(
            *(_run_single_task(t, tools_by_name, outputs, metrics) for t in level)
        )
        for tid, output in level_results:
            outputs[tid] = output

        if _level_trigger_fires(trigger, level, outputs):
            return outputs, level_idx

    return outputs, None


# -----------------------------------------------------------------------------
# Top-level entrypoint
# -----------------------------------------------------------------------------
async def run_dag_planner_replan(
    question: str,
    tools: list[Tool],
    llm: LLMProvider,
    max_replans: int = 2,
    trigger: TriggerKind = "any_failure",
    trace: Optional[dict[str, Any]] = None,
) -> tuple[str, AggregateMetrics]:
    """Plan → execute → check trigger → optionally replan → synthesize.

    Parameters
    ----------
    question, tools, llm:
        As for the base DAG planner.
    max_replans:
        Maximum number of replanner invocations (the initial plan does
        not count). When 0, behavior matches the base DAG planner.
    trigger:
        When to re-invoke the planner — see module docstring.
    trace:
        Optional sink populated with intermediate state for the verify
        script (history of all DAGs and their outputs, replan count,
        final synth state). Ignored when ``None``.
    """
    tools_by_name = {t.name: t for t in tools}
    metrics = AggregateMetrics()
    final_answer: str = ""
    history: list[tuple[DAG, dict[int, Any]]] = []
    last_dag: Optional[DAG] = None
    last_outputs: dict[int, Any] = {}

    if trace is not None:
        trace["initial_question"] = question
        trace["max_replans"] = max_replans
        trace["trigger"] = trigger
        trace["history"] = history  # populated by reference
        trace["replans_used"] = 0

    wall_clock_start = time.perf_counter()
    try:
        try:
            current_dag = await _do_plan_call(question, tools, llm, metrics)

            while True:
                outputs, fail_at_level = await _execute_with_trigger(
                    current_dag, tools_by_name, metrics, trigger
                )
                history.append((current_dag, outputs))
                last_dag = current_dag
                last_outputs = outputs

                if fail_at_level is None or metrics.n_replans >= max_replans:
                    break

                metrics.n_replans += 1
                if trace is not None:
                    trace["replans_used"] = metrics.n_replans
                logger.info(
                    "dag_planner_replan: replan #%d "
                    "(trigger=%s fired at level %d)",
                    metrics.n_replans,
                    trigger,
                    fail_at_level,
                )

                try:
                    current_dag = await _do_plan_call(
                        question, tools, llm, metrics, history=history
                    )
                except PlanValidationError as exc:
                    logger.warning(
                        "dag_planner_replan: replan #%d validation failed: %s",
                        metrics.n_replans,
                        exc,
                    )
                    break  # stop replanning; synth with what we have

            # -- Synth with the most recent DAG's outputs --------------------
            final_answer = await _synthesize(
                question,
                last_dag if last_dag is not None else current_dag,
                last_outputs,
                llm,
                metrics,
            )

            # -- empty_synth trigger (post-synth) ----------------------------
            if (
                trigger == "empty_synth"
                and metrics.n_replans < max_replans
                and _looks_like_refusal(final_answer)
            ):
                metrics.n_replans += 1
                if trace is not None:
                    trace["replans_used"] = metrics.n_replans
                logger.info(
                    "dag_planner_replan: empty_synth trigger fired, "
                    "replan #%d",
                    metrics.n_replans,
                )
                try:
                    current_dag = await _do_plan_call(
                        question, tools, llm, metrics, history=history
                    )
                    outputs, _ = await _execute_with_trigger(
                        current_dag, tools_by_name, metrics, "any_failure"
                    )
                    history.append((current_dag, outputs))
                    final_answer = await _synthesize(
                        question, current_dag, outputs, llm, metrics
                    )
                except PlanValidationError as exc:
                    logger.warning(
                        "dag_planner_replan: empty_synth replan validation "
                        "failed: %s",
                        exc,
                    )
        except PlanValidationError as exc:
            reason = f"plan validation failed — {exc}"
            logger.warning("dag_planner_replan: %s", reason)
            final_answer = f"{_EMPTY_RESULT_PREFIX}: {reason}"

        if not final_answer or not final_answer.strip():
            reason = (
                f"no answer produced after {metrics.n_replans} replan(s) "
                f"(trigger={trigger}, max_replans={max_replans})"
            )
            logger.warning("dag_planner_replan: %s", reason)
            final_answer = f"{_EMPTY_RESULT_PREFIX}: {reason}"
    finally:
        metrics.total_wall_clock_seconds = time.perf_counter() - wall_clock_start

    if trace is not None:
        trace["final_answer"] = final_answer

    return final_answer, metrics
