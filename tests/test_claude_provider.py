from __future__ import annotations

"""Pure-Python tests for the Claude provider's translation logic.

No live API calls — only verifies the Gemini-shaped shim and the
``messages`` → Anthropic translator behave correctly, including
tool_use_id pairing across parallel calls.
"""

import pytest

from src.llm.base import FunctionCall
from src.llm.claude import (
    _ClaudeCandidate,
    _ClaudeContent,
    _ClaudePart,
    _ClaudeResponse,
    _FunctionCallShim,
    _to_claude_messages,
    assistant_turn_from_response,
    extract_function_calls,
    extract_text,
    function_response_message,
)
from src.llm.gemini import set_active_provider


def _make_response(parts: list[_ClaudePart]) -> _ClaudeResponse:
    class _Usage:
        prompt_token_count = 0
        candidates_token_count = 0

    return _ClaudeResponse(
        candidates=[_ClaudeCandidate(_ClaudeContent(parts), "end_turn")],
        usage_metadata=_Usage(),
        raw_message=None,  # type: ignore[arg-type]
    )


def test_extract_function_calls_from_claude_response() -> None:
    response = _make_response(
        [
            _ClaudePart(text="Calling search..."),
            _ClaudePart(
                function_call=_FunctionCallShim("search", {"q": "python"}),
                tool_use_id="tu_1",
            ),
            _ClaudePart(
                function_call=_FunctionCallShim("search", {"q": "rust"}),
                tool_use_id="tu_2",
            ),
        ]
    )
    calls = extract_function_calls(response)
    assert calls == [
        FunctionCall(name="search", args={"q": "python"}),
        FunctionCall(name="search", args={"q": "rust"}),
    ]


def test_extract_text_from_claude_response() -> None:
    response = _make_response(
        [
            _ClaudePart(text="Hello "),
            _ClaudePart(text="world"),
        ]
    )
    assert extract_text(response) == "Hello world"


def test_assistant_turn_round_trips_parts() -> None:
    response = _make_response(
        [_ClaudePart(text="ok"), _ClaudePart(function_call=_FunctionCallShim("f", {"a": 1}), tool_use_id="tu_x")]
    )
    turn = assistant_turn_from_response(response)
    assert turn["role"] == "assistant"
    assert len(turn["content"]) == 2


def test_to_claude_messages_pairs_tool_use_ids_in_parallel() -> None:
    """Two parallel search() calls in one assistant turn → two
    function_response shims in the next user turn must pair by FIFO
    order to the assistant's tool_use_ids of the same name."""
    fc_part_a = _ClaudePart(
        function_call=_FunctionCallShim("search", {"q": "a"}),
        tool_use_id="tu_a",
    )
    fc_part_b = _ClaudePart(
        function_call=_FunctionCallShim("search", {"q": "b"}),
        tool_use_id="tu_b",
    )
    assistant_msg = {"role": "assistant", "content": [fc_part_a, fc_part_b]}

    resp_a = function_response_message("search", {"result": "alpha"})
    resp_b = function_response_message("search", {"result": "beta"})

    messages = [
        {"role": "user", "content": "find both"},
        assistant_msg,
        resp_a,
        resp_b,
    ]
    out = _to_claude_messages(messages)
    # user → assistant → user (the two responses merged)
    assert len(out) == 3
    assert out[0]["role"] == "user"
    assert out[1]["role"] == "assistant"
    assert out[2]["role"] == "user"
    tool_results = [b for b in out[2]["content"] if b.get("type") == "tool_result"]
    assert len(tool_results) == 2
    # FIFO order: first response pairs with first tool_use
    assert tool_results[0]["tool_use_id"] == "tu_a"
    assert tool_results[1]["tool_use_id"] == "tu_b"


def test_to_claude_messages_plain_text_user_turn() -> None:
    out = _to_claude_messages([{"role": "user", "content": "hello"}])
    assert out == [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]


def test_set_active_provider_round_trips_to_claude_helpers() -> None:
    """When active provider is Claude, the gemini.py-exported helpers
    delegate to claude.py — confirm extract_text works through dispatch."""
    set_active_provider("claude")
    try:
        from src.llm.gemini import extract_text as dispatch_extract_text

        response = _make_response([_ClaudePart(text="dispatched")])
        assert dispatch_extract_text(response) == "dispatched"
    finally:
        set_active_provider("gemini")
