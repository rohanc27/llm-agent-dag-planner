from __future__ import annotations

"""Aggregate per-task metrics, shared across strategies.

Each strategy accumulates one :class:`AggregateMetrics` per task by calling
:meth:`AggregateMetrics.add_call` with the :class:`~src.llm.base.CallMetrics`
returned from every LLM invocation.

``total_wall_clock_seconds`` semantics:

- Sequential strategies (ReAct): equals the sum of per-call latencies — set
  automatically by :meth:`add_call`.
- Parallel strategies (native parallel, DAG planner): the strategy measures
  wall-clock with :func:`time.perf_counter` around the gather call and
  overwrites :attr:`total_wall_clock_seconds` directly (and passes
  ``add_to_wall_clock=False`` to :meth:`add_call` so latencies don't get
  double-counted).

See SPEC.md § 3 Step 3.
"""

from dataclasses import dataclass, field
from typing import List

from src.llm.base import CallMetrics


@dataclass
class AggregateMetrics:
    """Per-task aggregate of per-call :class:`CallMetrics`."""

    n_llm_calls: int = 0
    # Total function calls EMITTED by the model across all turns. For ReAct
    # this may exceed the number actually executed — see
    # :attr:`discarded_parallel_calls`.
    n_tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    total_wall_clock_seconds: float = 0.0
    # Number of extra parallel function calls dropped by sequential
    # strategies (i.e. ReAct under Gemini, which lacks a native
    # disable_parallel_tool_use flag). Stays 0 for parallel strategies.
    discarded_parallel_calls: int = 0
    per_call: List[CallMetrics] = field(default_factory=list)

    def add_call(self, metrics: CallMetrics, add_to_wall_clock: bool = True) -> None:
        """Accumulate one LLM call.

        ``add_to_wall_clock=True`` (default) sums the call's latency into
        :attr:`total_wall_clock_seconds`, which is correct for sequential
        strategies. Parallel strategies should pass ``False`` and set
        :attr:`total_wall_clock_seconds` themselves.
        """
        self.n_llm_calls += 1
        self.n_tool_calls += metrics.n_tool_calls
        self.input_tokens += metrics.input_tokens
        self.output_tokens += metrics.output_tokens
        self.cost_usd += metrics.cost_usd
        if add_to_wall_clock:
            self.total_wall_clock_seconds += metrics.latency_seconds
        self.per_call.append(metrics)
