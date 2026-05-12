from __future__ import annotations

"""Native parallel tool-use strategy.

Same loop shape as :mod:`src.strategies.react`, but with two key differences:

* ``force_single_tool_call=False`` (the provider default) — Gemini may
  return multiple ``function_call`` parts per turn.
* The strategy executes *every* returned tool call concurrently with
  :func:`asyncio.gather` and emits N ``function_response`` parts back in
  a single user turn. Nothing is discarded.

For tasks with embarrassing parallelism (e.g. "what are the populations
of cities A and B?") this collapses several ReAct steps into one. For
strictly sequential dependencies, behavior collapses to ReAct.

Wall-clock accounting
---------------------
For ReAct, ``sum_of_per_call_latencies ≈ wall_clock`` because work is
serial. For native parallel, tool execution inside a turn overlaps, so
``sum_of_per_call_latencies`` *overcounts* the true wall clock.

We measure wall clock with :func:`time.perf_counter` around the whole
strategy and pass ``add_to_wall_clock=False`` to
:meth:`AggregateMetrics.add_call`, then assign
:attr:`AggregateMetrics.total_wall_clock_seconds` at the end. The
per-call latencies remain in ``metrics.per_call`` for breakdown
analysis. See SPEC.md § 3 Step 7.

To keep the strategy comparison fair, this loop deliberately reuses
:data:`src.strategies.react.REACT_SYSTEM_PROMPT` — the only experimental
difference between ReAct and native_parallel is the orchestration logic
(force_single_tool_call + drop-vs-gather), not the prompt.
"""

import asyncio
import logging
import time
from typing import Any, Optional

from google.genai import types

from src.llm.base import LLMProvider
from src.llm.gemini import (
    assistant_turn_from_response,
    extract_function_calls,
    extract_text,
)
from src.metrics import AggregateMetrics
from src.strategies.react import REACT_SYSTEM_PROMPT
from src.tools.base import Tool

logger = logging.getLogger(__name__)

MAX_STEPS: int = 10


async def _execute_one(
    tool: Optional[Tool], name: str, args: dict[str, Any]
) -> Any:
    """Run one tool call, surfacing errors back to the LLM as a string."""
    if tool is None:
        logger.warning("native_parallel: unknown tool %r", name)
        return f"Error: unknown tool {name!r}."
    try:
        return await tool.execute(**args)
    except Exception as exc:  # noqa: BLE001 — surface to the LLM
        logger.warning("native_parallel: tool %s raised: %s", name, exc)
        return f"Error executing {name}: {exc}"


def _parallel_function_responses_message(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    """Pack N ``(name, result)`` pairs into a single ``user``-role turn of
    ``function_response`` Parts.

    Gemini's accepted pattern for parallel tool-use:

        Content(role="user",  parts=[Part(text=...)])
        Content(role="model", parts=[Part(function_call=fc1), Part(function_call=fc2)])
        Content(role="user",  parts=[Part(function_response=fr1), Part(function_response=fr2)])
        Content(role="model", parts=[Part(text=...)])

    The N responses go into ONE user-role Content (not N separate turns),
    and pairing is by call name + position. We preserve the order
    returned by the model so duplicate-name calls (e.g. two
    ``wikipedia_search`` calls) line up correctly.
    """
    parts: list[types.Part] = []
    for name, result in pairs:
        payload: dict[str, Any] = (
            result if isinstance(result, dict) else {"result": result}
        )
        parts.append(types.Part.from_function_response(name=name, response=payload))
    return {"role": "user", "content": parts}


async def run_native_parallel(
    question: str,
    tools: list[Tool],
    llm: LLMProvider,
    system_prompt: Optional[str] = None,
    max_steps: int = MAX_STEPS,
) -> tuple[str, AggregateMetrics]:
    """Run native-parallel tool-use on a single question.

    Returns ``(final_answer, AggregateMetrics)``. ``total_wall_clock_seconds``
    is true wall clock (parallel tool execution overlaps) measured
    externally, not the sum of LLM-call latencies.
    """
    tools_by_name = {t.name: t for t in tools}
    tool_defs = [t.to_def() for t in tools]
    effective_system = (
        system_prompt if system_prompt is not None else REACT_SYSTEM_PROMPT
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    metrics = AggregateMetrics()
    final_answer: str = ""
    exhausted = True

    wall_clock_start = time.perf_counter()
    try:
        for step in range(max_steps):
            response, call_metrics = await llm.call(
                messages=messages,
                tools=tool_defs,
                system=effective_system,
                force_single_tool_call=False,
            )
            # Don't sum latency — wall clock is set from perf_counter below.
            metrics.add_call(call_metrics, add_to_wall_clock=False)

            function_calls = extract_function_calls(response)

            if not function_calls:
                final_answer = extract_text(response)
                exhausted = False
                break

            logger.info(
                "native_parallel step %d: %d call(s) — %s",
                step,
                len(function_calls),
                [{"name": c.name, "args": c.args} for c in function_calls],
            )

            # Count attempts against known tools (unknown-name calls don't
            # reach the external service — see _execute_one).
            metrics.n_tools_executed += sum(
                1 for c in function_calls if c.name in tools_by_name
            )

            # Concurrent tool execution, preserving call order.
            results = await asyncio.gather(
                *(
                    _execute_one(tools_by_name.get(c.name), c.name, c.args)
                    for c in function_calls
                )
            )

            # Round-trip into history: one model turn carrying all
            # function_call Parts, then one user turn carrying all
            # function_response Parts.
            messages.append(assistant_turn_from_response(response))
            messages.append(
                _parallel_function_responses_message(
                    list(zip((c.name for c in function_calls), results))
                )
            )

        if exhausted:
            logger.warning(
                "native_parallel exhausted max_steps=%d without a text-only response",
                max_steps,
            )
    finally:
        metrics.total_wall_clock_seconds = time.perf_counter() - wall_clock_start

    return final_answer, metrics
