from __future__ import annotations

"""Verify Step 1 (Gemini provider) end-to-end against Google AI Studio.

Two calls:
  1. No tools — "What is 2+2? Reply with just the number."
     Expected: ``n_tool_calls == 0``, ``stop_reason == "STOP"``.
  2. One mock ``get_weather`` tool — "What's the weather in San Francisco?"
     Expected: ``n_tool_calls >= 1``, ``stop_reason == "tool_use"``.

Run:

    python scripts/verify_step1.py

Requires ``GEMINI_API_KEY`` in ``.env`` (or the environment).
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Make ``src`` importable when running this file directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.llm.base import CallMetrics  # noqa: E402
from src.llm.gemini import GeminiProvider  # noqa: E402


def _print_metrics(label: str, metrics: CallMetrics) -> None:
    print(f"--- {label} ---")
    print(f"  latency_seconds : {metrics.latency_seconds:.3f}")
    print(f"  input_tokens    : {metrics.input_tokens}")
    print(f"  output_tokens   : {metrics.output_tokens}")
    print(f"  cost_usd        : ${metrics.cost_usd:.6f}")
    print(f"  n_tool_calls    : {metrics.n_tool_calls}")
    print(f"  stop_reason     : {metrics.stop_reason}")
    print()


def _extract_text(response) -> str:
    """Concatenate any text parts from the first candidate."""
    try:
        parts = response.candidates[0].content.parts or []
    except (AttributeError, IndexError, TypeError):
        return ""
    chunks = []
    for p in parts:
        text = getattr(p, "text", None)
        if text:
            chunks.append(text)
    return "".join(chunks).strip()


def _summarize_function_calls(response) -> list[dict]:
    """Pull out ``{name, args}`` for each function_call part."""
    try:
        parts = response.candidates[0].content.parts or []
    except (AttributeError, IndexError, TypeError):
        return []
    out = []
    for p in parts:
        fc = getattr(p, "function_call", None)
        if fc:
            # ``fc.args`` is dict-like in the google-genai SDK.
            args = dict(fc.args) if fc.args is not None else {}
            out.append({"name": fc.name, "args": args})
    return out


async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
        return 1

    provider = GeminiProvider()
    print(f"Using model: {provider.model}\n")

    # 1. Plain call, no tools.
    response_a, metrics_a = await provider.call(
        messages=[{"role": "user", "content": "What is 2+2? Reply with just the number."}],
        max_tokens=64,
    )
    text_a = _extract_text(response_a)
    print(f'Call 1 reply text: "{text_a}"')
    _print_metrics("Call 1 (no tools)", metrics_a)

    # 2. Call with a trivial mock tool. We do NOT execute it — we just want
    #    to see ``n_tool_calls`` increment.
    mock_tools = [
        {
            "name": "get_weather",
            "description": "Get the current weather for a given city.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city to look up weather for, e.g. 'San Francisco'.",
                    }
                },
                "required": ["city"],
            },
        }
    ]
    response_b, metrics_b = await provider.call(
        messages=[
            {"role": "user", "content": "What's the weather in San Francisco?"}
        ],
        tools=mock_tools,
        max_tokens=256,
    )
    fcs = _summarize_function_calls(response_b)
    print(f"Call 2 function_call parts: {fcs}")
    _print_metrics("Call 2 (with mock get_weather tool)", metrics_b)

    # Informational sanity checks.
    if metrics_a.n_tool_calls != 0:
        print("WARN: Call 1 unexpectedly produced function_call parts.")
    if metrics_b.n_tool_calls < 1:
        print(
            "WARN: Call 2 produced no function_call parts. "
            "Try re-running — Gemini's tool selection is occasionally probabilistic."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
