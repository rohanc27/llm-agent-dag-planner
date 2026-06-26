from __future__ import annotations

"""Sequential ReAct baseline.

Methodology note
----------------
Gemini has **no** native ``disable_parallel_tool_use`` flag (open feature
request as of late 2025). To enforce one-action-per-step ReAct semantics we
use two belt-and-suspenders mechanisms:

1. The provider call passes ``force_single_tool_call=True``, which injects a
   system-prompt hint asking for a single function per turn
   (see :mod:`src.llm.gemini`).
2. The strategy itself post-hoc keeps only the *first* function_call in any
   response and discards the rest. Discards are counted in
   :attr:`AggregateMetrics.discarded_parallel_calls` and logged at INFO.

This matches the original ReAct paper's "one action per step" contract; the
caveat is a Gemini-API constraint, not a design choice, and is called out in
the README per SPEC.md § 3 

ReAct does not currently use a separate "scratchpad" reasoning channel —
Gemini's tool-use loop is itself the reasoning trace.
"""

import logging
from typing import Any, Optional

from src.llm.base import LLMProvider
from src.llm.gemini import (
    assistant_turn_from_response,
    extract_function_calls,
    extract_text,
    function_response_message,
)
from src.metrics import AggregateMetrics
from src.tools.base import Tool

logger = logging.getLogger(__name__)

MAX_STEPS: int = 10

REACT_SYSTEM_PROMPT: str = (
    "You are a research assistant with access to Wikipedia tools. "
    "Use the tools to gather factual information before answering. "
    "When you have enough information, respond in plain text with a concise "
    "final answer and stop calling tools."
)


async def run_react(
    question: str,
    tools: list[Tool],
    llm: LLMProvider,
    system_prompt: Optional[str] = None,
    max_steps: int = MAX_STEPS,
) -> tuple[str, AggregateMetrics]:
    """Run sequential ReAct on a single question.

    Parameters
    ----------
    question:
        The user query (HotpotQA-style short question).
    tools:
        Available tools. The strategy hands their declarative defs to the
        provider and executes whichever the LLM selects.
    llm:
        Any :class:`LLMProvider`. For later iteration this is
        :class:`~src.llm.gemini.GeminiProvider`.
    system_prompt:
        Override the default ReAct system prompt.
    max_steps:
        Hard cap on (LLM call + tool execution) cycles.

    Returns
    -------
    tuple
        ``(final_answer, AggregateMetrics)``. If the loop exhausts
        ``max_steps`` without the model producing a text-only response,
        ``final_answer`` is an empty string and a warning is logged.
    """
    tools_by_name = {t.name: t for t in tools}
    tool_defs = [t.to_def() for t in tools]
    effective_system = system_prompt if system_prompt is not None else REACT_SYSTEM_PROMPT

    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    metrics = AggregateMetrics()
    final_answer: str = ""
    exhausted = True

    for step in range(max_steps):
        response, call_metrics = await llm.call(
            messages=messages,
            tools=tool_defs,
            system=effective_system,
            force_single_tool_call=True,
        )
        metrics.add_call(call_metrics)

        function_calls = extract_function_calls(response)

        if not function_calls:
            # No tool requested → treat the text as the final answer.
            final_answer = extract_text(response)
            exhausted = False
            break

        # Sequential semantics: keep only the first call, drop the rest.
        first_call, *extras = function_calls
        if extras:
            metrics.discarded_parallel_calls += len(extras)
            logger.info(
                "ReAct step %d: kept %s(%s); discarded %d extra parallel call(s): %s",
                step,
                first_call.name,
                first_call.args,
                len(extras),
                [{"name": c.name, "args": c.args} for c in extras],
            )

        # Execute the kept tool.
        tool = tools_by_name.get(first_call.name)
        if tool is None:
            tool_result: Any = f"Error: unknown tool {first_call.name!r}."
            logger.warning("ReAct step %d: unknown tool %r", step, first_call.name)
        else:
            # Count *attempted* executions — the external service may still
            # return an error, but the network/tool call did happen.
            metrics.n_tools_executed += 1
            try:
                tool_result = await tool.execute(**first_call.args)
            except Exception as exc:  # noqa: BLE001 — surface error to the LLM
                tool_result = f"Error executing {first_call.name}: {exc}"
                logger.warning(
                    "ReAct step %d: tool %s raised: %s", step, first_call.name, exc
                )

        # Round-trip into Gemini's message history: the model's response
        # (containing the function_call Part) goes back as an "assistant" turn,
        # followed by a "user" turn carrying the function_response Part.
        messages.append(assistant_turn_from_response(response))
        messages.append(function_response_message(first_call.name, tool_result))

    if exhausted:
        logger.warning(
            "ReAct exhausted max_steps=%d without a text-only response", max_steps
        )

    return final_answer, metrics
