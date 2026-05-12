from __future__ import annotations

"""Provider-agnostic tool dataclass.

A :class:`Tool` bundles the *declarative* surface an LLM sees (name,
description, JSON-Schema for inputs) with the *executable* surface a strategy
runs (an async callable). See SPEC.md § 3 Step 2.

Strategies pass ``[t.to_def() for t in tools]`` to the provider so the
provider never has to know about ``execute``.
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class Tool:
    """Self-describing async tool.

    Attributes
    ----------
    name:
        Stable identifier the LLM uses when emitting a function call.
    description:
        Free-text guidance shown to the LLM.
    input_schema:
        JSON-Schema (draft 2020-12 compatible) describing accepted arguments.
        Top-level should be ``{"type": "object", "properties": {...}, "required": [...]}``.
    execute:
        Async callable invoked with keyword arguments parsed from the LLM's
        function-call. Returns any JSON-serializable value.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    execute: Callable[..., Awaitable[Any]]

    def to_def(self) -> dict[str, Any]:
        """Return the declarative ``{name, description, input_schema}`` slice.

        Matches the :class:`src.llm.base.ToolDef` TypedDict shape.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
