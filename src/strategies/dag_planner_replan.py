from __future__ import annotations

"""DAG planner with adaptive replanning — Phase A contribution.

This is a thin shell around :mod:`src.strategies.dag_planner` that
addresses its biggest weakness on HotpotQA bridge: inability to recover
when an early retrieval returns the wrong article. The base strategy
plans up-front, executes, and synthesizes — if the search returns the
wrong page, there's no way back.

The strategy exposes six independently-controllable ablations so the
README and the ablation table can attribute each contribution cleanly:

  **Ablation 1: bounded replanning** (``max_replans`` parameter).
  The strategy re-invokes the planner up to ``max_replans`` times after
  a configurable trigger fires. Cap=0 reduces to the base DAG planner.

  **Ablation 2: refusal-detection trigger** (``trigger`` parameter).
  - ``any_failure``: re-plan after any in-DAG task returns
    ``{"error": ...}``, ``None``, ``""``, or ``[]``. Catches *syntactic*
    failures (placeholder errors, malformed plans, empty searches) but
    misses *semantic* failures (wrong-article retrieval that returned
    non-empty content).
  - ``all_failure``: like ``any_failure`` but requires every task in
    the level to fail.
  - ``empty_synth``: ignore in-DAG signals; instead, after the synth
    call, scan the final answer for refusal markers ("I cannot answer",
    "does not contain", "no information," …) and re-plan if found.
    This catches semantic failures that ``any_failure`` misses.

  **Ablation 3: fan-out retrieval** (``search_topk`` parameter).
  When ``search_topk > 1``, the planner system prompt is augmented with
  guidance to fetch the top-K search results in parallel (via
  ``$task_N.0``, ``$task_N.1``, …, ``$task_N.<K-1>`` placeholders),
  instead of relying on the top hit alone. This compensates for cases
  where the relevant article isn't ranked first.

  **Ablation 4: explicit diversification** (``diversify_replan`` flag).
  When set, the replan user prompt is augmented with (a) an enumeration
  of every prior search query and its top result, and (b) an explicit
  instruction not to repeat or paraphrase those queries — try a
  different entity, a different angle, or a more specific term. This
  addresses the "Big Fish musical composer lyricist" → "Big Fish
  musical composer and lyricist" near-identical-replan trap.

  **Ablation 5: rich replan context** (also controlled by
  ``diversify_replan``). When enabled, the prompt includes each prior
  task's full output (truncated to ~200 chars each), with the total
  history block bounded to ~3000 chars by dropping the oldest attempts
  when over budget. Gives the planner concrete evidence to reason from
  rather than only abstract failure signals.

  **Ablation 6: chain-of-thought synthesis** (``cot_synth`` flag).
  When set, the synth prompt asks the model to reason step-by-step and
  format its output as ``REASONING: ...\\nFINAL ANSWER: ...``. The
  ``FINAL ANSWER:`` clause is extracted as the eval-side
  ``predicted_answer``. Same LLM call as the non-CoT path — only the
  prompt is extended.

The replan loop itself:

  1. Initial planner call → DAG (LLM call 1).
  2. Execute the DAG level by level.
  3. After each level, check the configured trigger condition.
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
import re
import time
from typing import Any, Optional

try:
    from typing import Literal
except ImportError:  # pragma: no cover — Python <3.8
    from typing_extensions import Literal  # type: ignore[no-redef]

from src.core.dag import DAG, topological_levels
from src.llm.base import LLMProvider
from src.llm.gemini import extract_function_calls, extract_text
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
# Planner-prompt augmentation (Ablation 3: fan-out retrieval)
# -----------------------------------------------------------------------------
_TOPK_FANOUT_HINT_TEMPLATE: str = (
    "SEARCH FAN-OUT (top-{k} retrieval):\n"
    "For search-then-fetch patterns, fan out and fetch the top {k} search "
    "results in parallel rather than just the first one. After a search "
    "task returns a list of results, plan {k} fetch tasks at the next "
    "level — each independent of the others (no depends_on between them), "
    "each referencing a different result index by placeholder:\n"
    "  - first fetch:  args contains \"$task_N.0\"\n"
    "  - second fetch: args contains \"$task_N.1\"\n"
    "  - ...\n"
    "  - K-th fetch:   args contains \"$task_N.{k_minus_1}\"\n"
    "This compensates for cases where the top-ranked search hit is not "
    "the relevant article. Additional fetches in a level are cheap "
    "because they execute concurrently. Synth can then ignore irrelevant "
    "fetches. You may ignore this guidance if you are confident a single "
    "result suffices for the question."
)


def _build_planner_prompt(tools: list[Tool], search_topk: int) -> str:
    """Build the planner system prompt, optionally augmented for fan-out."""
    base = _planner_system_prompt(tools)
    if search_topk <= 1:
        return base
    hint = _TOPK_FANOUT_HINT_TEMPLATE.format(
        k=search_topk, k_minus_1=search_topk - 1
    )
    return f"{base}\n\n{hint}"


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


# ---------------------------------------------------------------------------
# Diversified replan prompt (Ablations 4 + 5)
# ---------------------------------------------------------------------------
_REPLAN_HISTORY_BUDGET_CHARS: int = 3000


def _build_replan_history_block(
    history: list[tuple[DAG, dict[int, Any]]],
    max_total_chars: int = _REPLAN_HISTORY_BUDGET_CHARS,
) -> str:
    """Render the per-task outputs of each prior attempt as a textual block.

    If the full history exceeds ``max_total_chars``, drop the oldest
    attempts and replace them with a placeholder so the most recent
    attempt(s) survive intact. This keeps the planner focused on what
    just happened without ballooning the prompt.
    """
    attempt_blocks: list[str] = []
    for i, (prior_dag, prior_outputs) in enumerate(history, start=1):
        block_lines = [f"--- Previous attempt #{i} ---"]
        for task in prior_dag.tasks:
            out = prior_outputs.get(task.id, "<not executed>")
            block_lines.append(
                f"  Task {task.id}: {task.tool}({task.args}) → "
                f"{_summarize_output(out, max_chars=200)}"
            )
        attempt_blocks.append("\n".join(block_lines))

    full = "\n\n".join(attempt_blocks)
    if len(full) <= max_total_chars:
        return full

    # Over budget: keep the most recent attempts, drop the rest.
    kept: list[str] = []
    used = 0
    for block in reversed(attempt_blocks):
        if used + len(block) + 2 > max_total_chars:
            break
        kept.insert(0, block)
        used += len(block) + 2
    n_dropped = len(attempt_blocks) - len(kept)
    if n_dropped > 0:
        kept.insert(
            0,
            f"({n_dropped} earlier attempt(s) omitted due to ~"
            f"{max_total_chars}-char context budget)",
        )
    return "\n\n".join(kept)


def _extract_search_summary(
    history: list[tuple[DAG, dict[int, Any]]],
) -> list[tuple[str, Any, Any]]:
    """Return (tool_name, query, top_result) for every search-shaped task
    across all prior attempts. The diversification instruction relies on
    this to tell the planner what NOT to re-query.
    """
    summary: list[tuple[str, Any, Any]] = []
    for prior_dag, prior_outputs in history:
        for task in prior_dag.tasks:
            if "search" not in task.tool.lower():
                continue
            query: Any = None
            for k, v in (task.args or {}).items():
                # Match common query-field names across our two benchmarks.
                if "query" in k.lower() or k == "q":
                    query = v
                    break
            if query is None:
                continue
            out = prior_outputs.get(task.id)
            if isinstance(out, list) and out:
                top = out[0]
            elif isinstance(out, dict) and "error" in out:
                top = f"<error: {out['error']}>"
            else:
                top = "<no results>"
            summary.append((task.tool, query, top))
    return summary


def _replan_user_message_diversified(
    question: str, history: list[tuple[DAG, dict[int, Any]]]
) -> str:
    """Replan prompt with explicit diversification + rich prior context."""
    history_block = _build_replan_history_block(history)
    search_summary = _extract_search_summary(history)
    if search_summary:
        search_lines = "\n".join(
            f"  - {tool}({query!r}) → top result: {top!r}"
            for tool, query, top in search_summary
        )
    else:
        search_lines = "  (no prior search queries to avoid)"

    return (
        f"QUESTION: {question}\n\n"
        f"Previous execution attempts and their concrete results:\n\n"
        f"{history_block}\n\n"
        f"The previous attempt produced a refusal answer. The previous "
        f"searches returned these top results:\n{search_lines}\n\n"
        f"Submit a NEW execution plan. Do not repeat the same search "
        f"queries or near-paraphrases of them. Try a fundamentally "
        f"different approach:\n"
        f"  - a different entity name (search for a related entity instead)\n"
        f"  - a more specific search term (add disambiguating words)\n"
        f"  - a different angle on the question (search for the property "
        f"directly rather than the entity)\n\n"
        f"If the prior outputs contained partial information that's relevant "
        f"to the question, use it directly in your plan's args (e.g. as a "
        f"literal title) rather than re-fetching the same articles."
    )


# ---------------------------------------------------------------------------
# Chain-of-thought synthesis (Ablation 6)
# ---------------------------------------------------------------------------
_FINAL_ANSWER_RE = re.compile(
    r"final\s*answer\s*:\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)

_COT_SYNTH_PROMPT_SUFFIX: str = (
    "\n\nThink step by step. What evidence is present in the tool outputs? "
    "What is the answer most likely to be? Reason explicitly, then provide "
    "the final answer.\n\n"
    "Format your response EXACTLY as:\n"
    "REASONING: <your step-by-step reasoning, 2-4 sentences>\n"
    "FINAL ANSWER: <the concise final answer in plain text>"
)


def _extract_final_answer(text: str) -> str:
    """Extract the substring after ``FINAL ANSWER:`` from a CoT response.

    Case-insensitive. Falls back to the whole stripped text if the marker
    is missing — better to ship a verbose-but-correct answer to the judge
    than to drop it because the model didn't follow format.
    """
    if not text:
        return ""
    m = _FINAL_ANSWER_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


async def _synthesize_cot(
    question: str,
    dag: DAG,
    outputs: dict[int, Any],
    llm: LLMProvider,
    metrics: AggregateMetrics,
    debug: Optional[dict[str, Any]] = None,
) -> str:
    """Same LLM call as :func:`_synthesize`, but the prompt asks for
    explicit step-by-step reasoning and we extract the ``FINAL ANSWER:``
    line from the response."""
    # Imported locally to avoid touching the base synth path.
    from src.strategies.dag_planner import _format_outputs_for_synthesis
    from src.strategies.react import REACT_SYSTEM_PROMPT

    user_msg = (
        f"Question: {question}\n\n"
        f"Tool execution results:\n"
        f"{_format_outputs_for_synthesis(dag, outputs)}\n\n"
        f"Using only the results above, answer the question."
        f"{_COT_SYNTH_PROMPT_SUFFIX}"
    )
    if debug is not None:
        debug["synth_system_prompt"] = REACT_SYSTEM_PROMPT
        debug["synth_user_prompt"] = user_msg
    response, call_metrics = await llm.call(
        messages=[{"role": "user", "content": user_msg}],
        system=REACT_SYSTEM_PROMPT,
    )
    metrics.add_call(call_metrics, add_to_wall_clock=False)
    raw = extract_text(response)
    if debug is not None:
        debug["synth_response_raw"] = raw
    final = _extract_final_answer(raw)
    if debug is not None:
        debug["synth_response"] = final
    return final


async def _do_plan_call(
    question: str,
    tools: list[Tool],
    llm: LLMProvider,
    metrics: AggregateMetrics,
    history: Optional[list[tuple[DAG, dict[int, Any]]]] = None,
    search_topk: int = 1,
    diversify_replan: bool = False,
) -> DAG:
    """One planner call. Raises :class:`PlanValidationError` on bad output."""
    if history:
        if diversify_replan:
            user_msg = _replan_user_message_diversified(question, history)
        else:
            user_msg = _replan_user_message(question, history)
    else:
        user_msg = question
    plan_response, plan_metrics = await llm.call(
        messages=[{"role": "user", "content": user_msg}],
        tools=[SUBMIT_PLAN_TOOL_DEF],
        system=_build_planner_prompt(tools, search_topk),
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
    search_topk: int = 1,
    diversify_replan: bool = False,
    cot_synth: bool = False,
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
    search_topk:
        If > 1, augment the planner system prompt to instruct the model
        to fan out and fetch the top-K search results in parallel rather
        than just the first one (Ablation 3). Default 1 disables fan-out.
    diversify_replan:
        If True, replans use the diversified prompt (Ablations 4 + 5):
        each prior search query + top result is enumerated explicitly,
        the planner is told not to repeat or paraphrase those queries,
        and full prior outputs are included as concrete evidence (bounded
        to ~3000 chars total).
    cot_synth:
        If True, synthesis uses a chain-of-thought prompt
        (Ablation 6) — ``REASONING:`` then ``FINAL ANSWER:`` — and the
        ``FINAL ANSWER:`` clause is extracted as the returned answer.
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
        trace["search_topk"] = search_topk
        trace["diversify_replan"] = diversify_replan
        trace["cot_synth"] = cot_synth
        trace["history"] = history  # populated by reference
        trace["replans_used"] = 0

    # Pick the synth function once — same signature either way.
    synth_fn = _synthesize_cot if cot_synth else _synthesize

    wall_clock_start = time.perf_counter()
    try:
        try:
            current_dag = await _do_plan_call(
                question, tools, llm, metrics, search_topk=search_topk
            )

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
                        question,
                        tools,
                        llm,
                        metrics,
                        history=history,
                        search_topk=search_topk,
                        diversify_replan=diversify_replan,
                    )
                except PlanValidationError as exc:
                    logger.warning(
                        "dag_planner_replan: replan #%d validation failed: %s",
                        metrics.n_replans,
                        exc,
                    )
                    break  # stop replanning; synth with what we have

            # -- Synth with the most recent DAG's outputs --------------------
            final_answer = await synth_fn(
                question,
                last_dag if last_dag is not None else current_dag,
                last_outputs,
                llm,
                metrics,
            )

            # -- empty_synth trigger (post-synth) ----------------------------
            # Looped: each replan may still produce a refusal, in which case
            # we replan again up to ``max_replans``. Earlier versions only
            # fired once, making cap2_empty and cap5_empty empirically
            # identical — that defeated the budget knob.
            while (
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
                        question,
                        tools,
                        llm,
                        metrics,
                        history=history,
                        search_topk=search_topk,
                        diversify_replan=diversify_replan,
                    )
                    outputs, _ = await _execute_with_trigger(
                        current_dag, tools_by_name, metrics, "any_failure"
                    )
                    history.append((current_dag, outputs))
                    final_answer = await synth_fn(
                        question, current_dag, outputs, llm, metrics
                    )
                except PlanValidationError as exc:
                    logger.warning(
                        "dag_planner_replan: empty_synth replan validation "
                        "failed: %s",
                        exc,
                    )
                    break  # bail out of the empty_synth loop on bad plan
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
