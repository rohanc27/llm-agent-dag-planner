from __future__ import annotations

"""LLM provider abstractions.

``base`` defines the provider-agnostic interface. ``gemini`` is the primary
provider; ``claude`` was added in Weekend 3 for the cross-LLM comparison
cells.
"""

from src.llm.base import CallMetrics, LLMProvider, ToolDef
from src.llm.claude import ClaudeProvider
from src.llm.gemini import GeminiProvider

__all__ = [
    "CallMetrics",
    "LLMProvider",
    "ToolDef",
    "GeminiProvider",
    "ClaudeProvider",
]
