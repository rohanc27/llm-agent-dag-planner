from __future__ import annotations

"""Gemini 2.5 Flash provider (Google AI Studio).

Primary LLM for Weekends 1 and 2. See SPEC.md § 3 Step 1.

Notes on parallel tool-use semantics
------------------------------------
Gemini has **no** native ``disable_parallel_tool_use`` switch — this is an
open feature request as of late 2025. The ``force_single_tool_call`` flag here
only injects a system-prompt hint asking for one function per turn; the
strategies layer (Step 3 ReAct) also discards any extra function_call parts
post-hoc. Belt and suspenders.
"""

import os
import time
from typing import Any, Optional

from google import genai
from google.genai import types

from src.llm.base import CallMetrics, LLMProvider, ToolDef

# -----------------------------------------------------------------------------
# Gemini 2.5 Flash — Google AI Studio paid-tier pricing as of May 2026.
# The user is on the FREE tier; these constants exist for cost-reporting in
# benchmark output so cross-provider comparisons are meaningful.
# -----------------------------------------------------------------------------
INPUT_COST_PER_MTOK: float = 0.30   # USD per 1M input tokens
OUTPUT_COST_PER_MTOK: float = 2.50  # USD per 1M output tokens

DEFAULT_MODEL: str = "gemini-2.5-flash"

# System hint appended when force_single_tool_call=True (no native API flag).
_SINGLE_CALL_HINT: str = (
    "When using tools, call exactly one function per turn, then wait for "
    "the result before deciding the next step."
)


def _compute_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        (input_tokens / 1_000_000.0) * INPUT_COST_PER_MTOK
        + (output_tokens / 1_000_000.0) * OUTPUT_COST_PER_MTOK
    )


def _to_gemini_contents(messages: list[dict[str, Any]]) -> list[types.Content]:
    """Translate ``[{"role","content"}, ...]`` into Gemini ``Content`` objects.

    Role mapping: ``user`` → ``user``, ``assistant`` → ``model``. Anything
    already shaped as a list of Parts is forwarded as-is so callers can attach
    function-call / function-response parts in later steps.
    """
    contents: list[types.Content] = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "assistant":
            role = "model"
        content = msg.get("content", "")
        if isinstance(content, str):
            parts: list[types.Part] = [types.Part.from_text(text=content)]
        elif isinstance(content, list):
            # Caller already provided Part objects (or dicts the SDK accepts).
            parts = content  # type: ignore[assignment]
        else:
            parts = [types.Part.from_text(text=str(content))]
        contents.append(types.Content(role=role, parts=parts))
    return contents


def _to_gemini_tools(tools: list[ToolDef]) -> list[types.Tool]:
    """Wrap our ``ToolDef`` list in a single ``types.Tool`` with
    function declarations — the shape Gemini's API expects."""
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=t["input_schema"],
                )
                for t in tools
            ]
        )
    ]


def _count_function_calls(response: Any) -> int:
    """Count ``function_call`` parts on the first candidate's content."""
    try:
        candidate = response.candidates[0]
        parts = candidate.content.parts or []
    except (AttributeError, IndexError, TypeError):
        return 0
    return sum(1 for p in parts if getattr(p, "function_call", None))


def _stop_reason(response: Any, n_tool_calls: int) -> Optional[str]:
    """Return ``"tool_use"`` if any function_call part exists, otherwise the
    Gemini ``finish_reason`` enum name (e.g. ``"STOP"``, ``"MAX_TOKENS"``)."""
    if n_tool_calls > 0:
        return "tool_use"
    try:
        finish_reason = response.candidates[0].finish_reason
    except (AttributeError, IndexError):
        return None
    if finish_reason is None:
        return None
    return getattr(finish_reason, "name", str(finish_reason))


class GeminiProvider(LLMProvider):
    """Async Gemini 2.5 Flash provider with metric instrumentation."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        # The google-genai SDK exposes async methods under ``.aio`` on the
        # Client. We hold the async accessor directly.
        self._client = genai.Client(
            api_key=api_key or os.environ.get("GEMINI_API_KEY")
        ).aio

    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolDef]] = None,
        system: Optional[str] = None,
        force_single_tool_call: bool = False,
        max_tokens: int = 4096,
    ) -> tuple[Any, CallMetrics]:
        # force_single_tool_call has no API equivalent on Gemini — fall back
        # to a system-prompt hint. Strategies must still drop extras.
        effective_system = system
        if force_single_tool_call:
            effective_system = (
                f"{system}\n\n{_SINGLE_CALL_HINT}" if system else _SINGLE_CALL_HINT
            )

        config_kwargs: dict[str, Any] = {"max_output_tokens": max_tokens}
        if effective_system is not None:
            config_kwargs["system_instruction"] = effective_system
        if tools:
            config_kwargs["tools"] = _to_gemini_tools(tools)
        config = types.GenerateContentConfig(**config_kwargs)

        contents = _to_gemini_contents(messages)

        start = time.perf_counter()
        response = await self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        latency = time.perf_counter() - start

        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)

        n_tool_calls = _count_function_calls(response)

        metrics = CallMetrics(
            latency_seconds=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=_compute_cost(input_tokens, output_tokens),
            n_tool_calls=n_tool_calls,
            stop_reason=_stop_reason(response, n_tool_calls),
        )
        return response, metrics
