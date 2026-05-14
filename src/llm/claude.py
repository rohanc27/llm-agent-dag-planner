from __future__ import annotations

"""Anthropic Claude Sonnet 4.6 provider.

Added in Weekend 3 for the cross-LLM comparison cells (see SPEC.md § 4
Step 14). Strategies stay LLM-agnostic by importing helper functions
from :mod:`src.llm.gemini`; when run-time provider is Claude, those
helpers transparently delegate here. This keeps the strategy code
unchanged.

Tool-use protocol notes
-----------------------
Anthropic returns assistant messages as a list of content blocks
(``TextBlock``, ``ToolUseBlock``). Each ``ToolUseBlock`` carries an
``id`` that the matching ``tool_result`` user-block must reference.
We re-emit the *exact* assistant ``content`` list back into the next
``messages.create`` call, so tool_use IDs survive the round-trip
naturally. Function-response user turns are merged into one
``tool_result`` user message before being sent to Anthropic.

Pricing
-------
Sonnet 4.6 list pricing as of May 2026: $3 / $15 per MTok in/out.
"""

import asyncio
import os
import time
from typing import Any, Optional

from anthropic import AsyncAnthropic
from anthropic.types import (
    Message,
    TextBlock,
    ToolUseBlock,
)

from src.llm.base import CallMetrics, FunctionCall, LLMProvider, ToolDef

INPUT_COST_PER_MTOK: float = 3.00
OUTPUT_COST_PER_MTOK: float = 15.00

DEFAULT_MODEL: str = "claude-sonnet-4-5"

_RPM_MAX_RETRIES: int = 5
_RATE_LIMIT_BACKOFF_BASE: float = 4.0
_RATE_LIMIT_MAX_DELAY: float = 65.0


# -----------------------------------------------------------------------------
# Internal shim objects that pose as Gemini-style "Parts" so the gemini.py
# helpers (``extract_function_calls`` / ``extract_text`` /
# ``assistant_turn_from_response``) keep working when the underlying
# provider is Claude. We attach the Anthropic ``tool_use`` ``id`` to the
# shim so it survives round-trips through the message history.
# -----------------------------------------------------------------------------


class _FunctionCallShim:
    """Mimics Gemini ``function_call`` (``.name``, ``.args``)."""

    __slots__ = ("name", "args")

    def __init__(self, name: str, args: dict[str, Any]) -> None:
        self.name = name
        self.args = args


class _ClaudePart:
    """Duck-typed Gemini ``Part`` with ``text``/``function_call``/
    ``function_response`` attributes. Strategies never construct these
    directly — :func:`assistant_turn_from_response` and
    :func:`function_response_message` build them.
    """

    __slots__ = ("text", "function_call", "function_response", "tool_use_id")

    def __init__(
        self,
        text: Optional[str] = None,
        function_call: Optional[_FunctionCallShim] = None,
        function_response: Optional[tuple[str, Any]] = None,
        tool_use_id: Optional[str] = None,
    ) -> None:
        self.text = text
        self.function_call = function_call
        self.function_response = function_response  # (name, payload)
        self.tool_use_id = tool_use_id


class _ClaudeContent:
    __slots__ = ("parts", "role")

    def __init__(self, parts: list[_ClaudePart], role: str = "model") -> None:
        self.parts = parts
        self.role = role


class _ClaudeCandidate:
    __slots__ = ("content", "finish_reason")

    def __init__(self, content: _ClaudeContent, finish_reason: Optional[str]) -> None:
        self.content = content
        self.finish_reason = finish_reason


class _ClaudeResponse:
    """Gemini-response-shaped wrapper. Exposes ``.candidates[0].content.parts``
    so the gemini.py helpers can read it. Also carries ``usage_metadata``
    for the metric path."""

    __slots__ = ("candidates", "usage_metadata", "_raw_message")

    def __init__(
        self,
        candidates: list[_ClaudeCandidate],
        usage_metadata: Any,
        raw_message: Message,
    ) -> None:
        self.candidates = candidates
        self.usage_metadata = usage_metadata
        self._raw_message = raw_message


class _UsageShim:
    __slots__ = ("prompt_token_count", "candidates_token_count")

    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.prompt_token_count = input_tokens
        self.candidates_token_count = output_tokens


# -----------------------------------------------------------------------------
# Provider-side helper implementations (Claude). These mirror the names in
# ``src.llm.gemini`` so the dispatcher there can delegate to us.
# -----------------------------------------------------------------------------
def extract_function_calls(response: _ClaudeResponse) -> list[FunctionCall]:
    parts = response.candidates[0].content.parts or []
    out: list[FunctionCall] = []
    for p in parts:
        fc = getattr(p, "function_call", None)
        if fc is None:
            continue
        out.append(FunctionCall(name=fc.name, args=dict(fc.args or {})))
    return out


def extract_text(response: _ClaudeResponse) -> str:
    parts = response.candidates[0].content.parts or []
    return "".join((getattr(p, "text", "") or "") for p in parts).strip()


def assistant_turn_from_response(response: _ClaudeResponse) -> dict[str, Any]:
    parts = list(response.candidates[0].content.parts or [])
    return {"role": "assistant", "content": parts}


def function_response_message(name: str, result: Any) -> dict[str, Any]:
    """Build a user turn carrying one function_response shim part.

    Tool-use-id pairing happens lazily in :func:`_to_claude_messages` —
    we match by FIFO order against the most recent assistant turn's
    tool_use parts of the same name.
    """
    payload: dict[str, Any] = result if isinstance(result, dict) else {"result": result}
    part = _ClaudePart(function_response=(name, payload))
    return {"role": "user", "content": [part]}


# -----------------------------------------------------------------------------
# Translation: history (list of {"role","content"}) → Anthropic Messages
# -----------------------------------------------------------------------------
def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    import json

    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        return str(value)


def _to_claude_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Translate provider-neutral history into Anthropic message format.

    Pairs ``function_response`` shim parts with their originating
    ``tool_use`` block IDs by FIFO order against the most recent
    assistant turn. Adjacent user turns are merged so the user/assistant
    alternation Anthropic requires is preserved.
    """
    out: list[dict[str, Any]] = []
    # FIFO queue of pending tool_use_ids from the most recent assistant turn,
    # grouped by name so duplicate-name parallel calls pair in order.
    pending_ids: dict[str, list[str]] = {}

    def _flush_user_buffer(buf: list[dict[str, Any]]) -> None:
        if not buf:
            return
        # All entries in buf are content blocks; merge into one user turn.
        merged: list[dict[str, Any]] = []
        for entry in buf:
            merged.extend(entry)
        out.append({"role": "user", "content": merged})

    user_buffer: list[list[dict[str, Any]]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "user":
            blocks: list[dict[str, Any]] = []
            if isinstance(content, str):
                if content:
                    blocks.append({"type": "text", "text": content})
            elif isinstance(content, list):
                # Could be a list of _ClaudePart (function_response shims),
                # or a list of plain dicts already, or raw text/Part objects.
                for part in content:
                    if isinstance(part, _ClaudePart):
                        if part.function_response is not None:
                            fname, payload = part.function_response
                            queue = pending_ids.get(fname) or []
                            if queue:
                                tid = queue.pop(0)
                            else:
                                # Fallback: scan all queues for any pending id.
                                tid = None
                                for q in pending_ids.values():
                                    if q:
                                        tid = q.pop(0)
                                        break
                                if tid is None:
                                    # Skip — Anthropic would reject a
                                    # tool_result without a paired tool_use.
                                    continue
                            blocks.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tid,
                                    "content": _stringify(payload),
                                }
                            )
                        elif part.text:
                            blocks.append({"type": "text", "text": part.text})
                    elif isinstance(part, dict):
                        blocks.append(part)
                    else:
                        # Unknown part type — coerce to text.
                        txt = getattr(part, "text", None)
                        if txt:
                            blocks.append({"type": "text", "text": txt})
            elif content:
                blocks.append({"type": "text", "text": str(content)})
            if blocks:
                user_buffer.append(blocks)
            continue

        # role == "assistant" / "model"
        _flush_user_buffer(user_buffer)
        user_buffer = []
        pending_ids = {}

        a_blocks: list[dict[str, Any]] = []
        if isinstance(content, str):
            if content:
                a_blocks.append({"type": "text", "text": content})
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, _ClaudePart):
                    if part.function_call is not None:
                        tid = part.tool_use_id or f"tool_{len(a_blocks)}"
                        fc = part.function_call
                        a_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tid,
                                "name": fc.name,
                                "input": dict(fc.args or {}),
                            }
                        )
                        pending_ids.setdefault(fc.name, []).append(tid)
                    elif part.text:
                        a_blocks.append({"type": "text", "text": part.text})
                elif isinstance(part, dict):
                    a_blocks.append(part)
                    if part.get("type") == "tool_use":
                        pending_ids.setdefault(
                            part["name"], []
                        ).append(part["id"])
                else:
                    txt = getattr(part, "text", None)
                    if txt:
                        a_blocks.append({"type": "text", "text": txt})
        if a_blocks:
            out.append({"role": "assistant", "content": a_blocks})

    _flush_user_buffer(user_buffer)
    return out


def _to_claude_tools(tools: list[ToolDef]) -> list[dict[str, Any]]:
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["input_schema"],
        }
        for t in tools
    ]


def _is_rate_limit_error(exc: BaseException) -> bool:
    msg = str(exc)
    return "429" in msg or "rate_limit" in msg.lower()


def _is_transient_server_error(exc: BaseException) -> bool:
    msg = str(exc)
    return any(code in msg for code in ("500", "502", "503", "529"))


def _compute_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        (input_tokens / 1_000_000.0) * INPUT_COST_PER_MTOK
        + (output_tokens / 1_000_000.0) * OUTPUT_COST_PER_MTOK
    )


def _claude_message_to_response(message: Message) -> _ClaudeResponse:
    """Wrap an Anthropic ``Message`` in a Gemini-shaped shim."""
    parts: list[_ClaudePart] = []
    for block in message.content:
        if isinstance(block, TextBlock):
            parts.append(_ClaudePart(text=block.text))
        elif isinstance(block, ToolUseBlock):
            args = block.input if isinstance(block.input, dict) else {}
            parts.append(
                _ClaudePart(
                    function_call=_FunctionCallShim(block.name, dict(args)),
                    tool_use_id=block.id,
                )
            )
    usage = _UsageShim(
        input_tokens=int(getattr(message.usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(message.usage, "output_tokens", 0) or 0),
    )
    stop_reason = message.stop_reason or None
    return _ClaudeResponse(
        candidates=[_ClaudeCandidate(_ClaudeContent(parts), stop_reason)],
        usage_metadata=usage,
        raw_message=message,
    )


def _count_function_calls(message: Message) -> int:
    return sum(1 for b in message.content if isinstance(b, ToolUseBlock))


def _stop_reason_for_metric(message: Message, n_tool_calls: int) -> Optional[str]:
    if n_tool_calls > 0:
        return "tool_use"
    return message.stop_reason or None


class ClaudeProvider(LLMProvider):
    """Async Anthropic Claude provider with metric instrumentation."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        self._client = AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )

    async def _create_with_retry(self, **kwargs: Any) -> Message:
        attempt = 0
        while True:
            try:
                return await self._client.messages.create(**kwargs)
            except Exception as exc:  # noqa: BLE001
                is_rate_limit = _is_rate_limit_error(exc)
                is_server_5xx = _is_transient_server_error(exc)
                if not (is_rate_limit or is_server_5xx):
                    raise
                if attempt >= _RPM_MAX_RETRIES:
                    raise
                delay = min(
                    _RATE_LIMIT_BACKOFF_BASE * (2 ** attempt),
                    _RATE_LIMIT_MAX_DELAY,
                )
                kind = "rate_limit" if is_rate_limit else "5xx"
                print(
                    f"[claude retry] {kind} — sleeping {delay:.1f}s "
                    f"(attempt {attempt + 1}/{_RPM_MAX_RETRIES})",
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
        claude_messages = _to_claude_messages(messages)

        request: dict[str, Any] = {
            "model": self.model,
            "messages": claude_messages,
            "max_tokens": max_tokens,
        }
        if system is not None:
            request["system"] = system
        if tools:
            request["tools"] = _to_claude_tools(tools)
            if force_single_tool_call:
                # Native Anthropic parallel-tool-use disable flag.
                request["tool_choice"] = {
                    "type": "auto",
                    "disable_parallel_tool_use": True,
                }
            if forced_function_name is not None:
                request["tool_choice"] = {
                    "type": "tool",
                    "name": forced_function_name,
                    "disable_parallel_tool_use": True,
                }

        start = time.perf_counter()
        message = await self._create_with_retry(**request)
        latency = time.perf_counter() - start

        response = _claude_message_to_response(message)
        n_tool_calls = _count_function_calls(message)

        metrics = CallMetrics(
            latency_seconds=latency,
            input_tokens=int(getattr(message.usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(message.usage, "output_tokens", 0) or 0),
            cost_usd=_compute_cost(
                int(getattr(message.usage, "input_tokens", 0) or 0),
                int(getattr(message.usage, "output_tokens", 0) or 0),
            ),
            n_tool_calls=n_tool_calls,
            stop_reason=_stop_reason_for_metric(message, n_tool_calls),
        )
        return response, metrics
