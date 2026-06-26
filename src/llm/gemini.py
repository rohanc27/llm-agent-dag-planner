from __future__ import annotations

"""Gemini 2.5 Flash provider (Google AI Studio).

Primary LLM provider.

Notes on parallel tool-use semantics
------------------------------------
Gemini has **no** native ``disable_parallel_tool_use`` switch — this is an
open feature request as of late 2025. The ``force_single_tool_call`` flag here
only injects a system-prompt hint asking for one function per turn; the
strategies layer (earlier milestone ReAct) also discards any extra function_call parts
post-hoc. Belt and suspenders.
"""

import asyncio
import os
import re
import time
from typing import Any, Optional

from google import genai
from google.genai import types

from src.llm.base import CallMetrics, FunctionCall, LLMProvider, ToolDef

# -----------------------------------------------------------------------------
# Active-provider dispatch hook
# -----------------------------------------------------------------------------
# Strategy modules import the four response helpers below from this module by
# ``run_eval`` flips this at startup based on ``--llm``.
_active_provider: str = "gemini"


def set_active_provider(name: str) -> None:
    """Set the active LLM provider helper dispatch."""
    if name != "gemini":
        raise ValueError(f"unknown provider {name!r}")

    global _active_provider
    _active_provider = "gemini"



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

# Rate-limit retry knobs. AI Studio free-tier limits on gemini-2.5-flash
# observed empirically as 5 RPM and 20 RPD (the public docs sometimes list
# different numbers). We honour Gemini's suggested ``retryDelay`` from the
# 429 body when present, otherwise fall back to exponential backoff.
#
# Per-minute exhaustion clears in <60s, so retries usually succeed. Per-day
# exhaustion implies the rolling-24h cap is full; retries may still progress
# (slots age out one at a time) but each call needs a full wait, so we
# bound it more tightly and surface a clearer error.
_RPM_MAX_RETRIES: int = 5
_RPD_MAX_RETRIES: int = 2
_RATE_LIMIT_BACKOFF_BASE: float = 4.0
_RATE_LIMIT_MAX_DELAY: float = 65.0  # cap suggested delays at this many seconds


def _parse_retry_delay_seconds(exc_text: str) -> Optional[float]:
    """Extract Gemini's suggested ``retryDelay`` (in seconds) from a 429 body."""
    m = re.search(
        r"['\"]retryDelay['\"]\s*:\s*['\"](\d+(?:\.\d+)?)s['\"]", exc_text
    )
    return float(m.group(1)) if m else None


def _is_rate_limit_error(exc: BaseException) -> bool:
    """True for the Gemini 429 / RESOURCE_EXHAUSTED quota-exceeded shape."""
    msg = str(exc)
    return "429" in msg and "RESOURCE_EXHAUSTED" in msg


def _is_transient_server_error(exc: BaseException) -> bool:
    """True for transient Gemini-side errors that are safe to retry —
    503 UNAVAILABLE and 500 INTERNAL. These fire when Gemini is
    overloaded; retrying after a short backoff usually succeeds.
    """
    msg = str(exc)
    return ("503" in msg and "UNAVAILABLE" in msg) or (
        "500" in msg and "INTERNAL" in msg
    )


def _is_per_day_quota(exc_text: str) -> bool:
    """True if the error is the daily (rolling-24h) free-tier cap."""
    return "PerDay" in exc_text or "RequestsPerDay" in exc_text


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


# -----------------------------------------------------------------------------
# Public response-decoding helpers (used by strategies). These intentionally
# live in the concrete provider module — strategies import what they need
# rather than the abstract base growing a provider-specific surface.
# -----------------------------------------------------------------------------
def extract_function_calls(response: Any) -> list[FunctionCall]:
    """Return every ``function_call`` part on the first candidate.

    Each entry carries the tool ``name`` and a plain-dict ``args`` payload
    (the SDK's ``MapComposite`` is converted to a regular ``dict``).
    """
    out: list[FunctionCall] = []
    try:
        parts = response.candidates[0].content.parts or []
    except (AttributeError, IndexError, TypeError):
        return out
    for p in parts:
        fc = getattr(p, "function_call", None)
        if fc is None:
            continue
        args = dict(fc.args) if fc.args is not None else {}
        out.append(FunctionCall(name=fc.name, args=args))
    return out


def extract_text(response: Any) -> str:
    """Concatenate every text part on the first candidate's content."""
    try:
        parts = response.candidates[0].content.parts or []
    except (AttributeError, IndexError, TypeError):
        return ""
    return "".join(getattr(p, "text", "") or "" for p in parts).strip()


def assistant_turn_from_response(response: Any) -> dict[str, Any]:
    """Wrap the model's response as a ``{"role": "assistant", ...}`` message.

    Forwards the response's Parts list as-is so function_call Parts survive
    the round-trip into the next call. :func:`_to_gemini_contents` translates
    ``assistant`` → ``model`` and forwards Parts directly.
    """
    try:
        parts = list(response.candidates[0].content.parts or [])
    except (AttributeError, IndexError, TypeError):
        parts = []
    return {"role": "assistant", "content": parts}


def function_response_message(name: str, result: Any) -> dict[str, Any]:
    """Build a ``{"role": "user", ...}`` turn carrying one function_response.

    Gemini requires the ``response`` payload to be a dict; scalars/lists get
    wrapped as ``{"result": ...}`` so callers can pass strings, lists, or
    dicts uniformly.
    """
    payload: dict[str, Any] = result if isinstance(result, dict) else {"result": result}
    part = types.Part.from_function_response(name=name, response=payload)
    return {"role": "user", "content": [part]}


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

    async def _generate_with_retry(
        self,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> Any:
        """``generate_content`` wrapped in 429-aware retry.

        Honours Gemini's suggested ``retryDelay`` when present, otherwise
        falls back to exponential backoff. Per-day exhaustion retries fewer
        times because each retry needs a full wait for a slot to age out.
        Non-429 errors propagate immediately.
        """
        attempt = 0
        while True:
            try:
                return await self._client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:  # noqa: BLE001
                exc_text = str(exc)
                is_rate_limit = _is_rate_limit_error(exc)
                is_server_5xx = _is_transient_server_error(exc)
                if not (is_rate_limit or is_server_5xx):
                    raise
                if is_rate_limit:
                    per_day = _is_per_day_quota(exc_text)
                    max_retries = (
                        _RPD_MAX_RETRIES if per_day else _RPM_MAX_RETRIES
                    )
                    kind = "PerDay" if per_day else "PerMinute"
                else:
                    # 503/500 — exponential backoff, modest retry budget.
                    max_retries = _RPM_MAX_RETRIES
                    kind = "5xx"
                if attempt >= max_retries:
                    raise
                suggested = _parse_retry_delay_seconds(exc_text)
                if suggested is not None:
                    delay = suggested + 1.0  # +1s margin
                else:
                    delay = _RATE_LIMIT_BACKOFF_BASE * (2 ** attempt)
                delay = min(delay, _RATE_LIMIT_MAX_DELAY)
                print(
                    f"[gemini retry] {kind} — sleeping {delay:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})",
                    flush=True,
                )
                await asyncio.sleep(delay)
                attempt += 1

    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolDef]] = None,
        system: Optional[str] = None,
        force_single_tool_call: bool = False,
        max_tokens: int = 4096,
        forced_function_name: Optional[str] = None,
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
        # ``forced_function_name`` pins the model to a single function via
        # Gemini's ``tool_config``. Used by the DAG planner to force a
        # ``submit_plan`` call. Has no effect when ``tools`` is empty.
        if forced_function_name is not None and tools:
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=[forced_function_name],
                )
            )
        config = types.GenerateContentConfig(**config_kwargs)

        contents = _to_gemini_contents(messages)

        # ``latency_seconds`` is measured around the full retry loop, so
        # rate-limit waits show up in the benchmark numbers — that's the
        # honest wall-clock cost of running on the free tier.
        start = time.perf_counter()
        response = await self._generate_with_retry(contents=contents, config=config)
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
