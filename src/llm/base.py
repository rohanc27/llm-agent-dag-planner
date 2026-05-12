from __future__ import annotations

"""Provider-agnostic LLM interface.

Strategies (ReAct, native parallel, DAG planner) call providers exclusively
through :class:`LLMProvider`, so swapping Gemini for Claude in Weekend 3 is a
one-line wiring change. See SPEC.md § 3 Step 1.

The ``Response`` type is intentionally provider-native — each strategy decodes
function-call blocks using helpers in the concrete provider module. Only the
:class:`CallMetrics` shape is uniform across providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, TypedDict


class ToolDef(TypedDict):
    """Provider-agnostic tool definition.

    The real :class:`src.tools.base.Tool` dataclass (Step 2) will carry the
    same three fields plus an ``execute`` callable. Providers only need the
    declarative part to pass to the model.
    """

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class CallMetrics:
    """Per-call instrumentation record (uniform across providers)."""

    latency_seconds: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    n_tool_calls: int
    stop_reason: Optional[str]


class LLMProvider(ABC):
    """Abstract base for LLM providers.

    All providers expose a single async ``call`` method returning the
    provider-native response plus a :class:`CallMetrics` record.
    """

    @abstractmethod
    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolDef]] = None,
        system: Optional[str] = None,
        force_single_tool_call: bool = False,
        max_tokens: int = 4096,
    ) -> tuple[Any, CallMetrics]:
        """Issue one model call.

        Parameters
        ----------
        messages:
            Chat history as a list of ``{"role", "content"}`` dicts. Roles are
            ``"user"`` and ``"assistant"`` (providers translate as needed).
        tools:
            Declarative tool definitions; ``None`` disables tool use.
        system:
            Optional system prompt.
        force_single_tool_call:
            Best-effort request for one function call per turn. Some providers
            (Claude) support this natively; others (Gemini) only via a system
            hint, so strategies must also discard extras post-hoc.
        max_tokens:
            Output token cap.
        """
        raise NotImplementedError
