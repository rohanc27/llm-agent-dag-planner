from __future__ import annotations

"""Shared DAG core for the planner family of strategies.

A planning strategy submits a list of tasks; this module:

* validates the shape (cycle-free, all dependencies resolvable),
* groups tasks into *topological levels* — within each level, tasks have
  no remaining dependencies and can therefore execute concurrently,
* substitutes ``"$task_<id>"`` and ``"$task_<id>.field"`` placeholders in
  task args with prior outputs at execution time.

The same module is consumed by :mod:`src.strategies.dag_planner` today
and the LangGraph / ADK variants in later iteration.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Task:
    """One node in a planned DAG."""

    id: int
    tool: str
    args: dict[str, Any]
    depends_on: list[int] = field(default_factory=list)


@dataclass
class DAG:
    """A directed acyclic graph of tasks."""

    tasks: list[Task]


def topological_levels(dag: DAG) -> list[list[Task]]:
    """Group ``dag.tasks`` into levels by topological order (Kahn's algorithm).

    Tasks within a level have no remaining dependencies and can run
    concurrently. Within each level, tasks are sorted by id for stable
    output across runs.

    Raises
    ------
    ValueError
        If the DAG contains a cycle, references a missing task id, or has
        duplicate task ids.
    """
    task_by_id: dict[int, Task] = {}
    for t in dag.tasks:
        if t.id in task_by_id:
            raise ValueError(f"Duplicate task id {t.id}")
        task_by_id[t.id] = t

    # Validate dependency references up front so we get a clear error
    # instead of a silent "no progress" cycle-like outcome.
    for t in dag.tasks:
        for dep in t.depends_on:
            if dep not in task_by_id:
                raise ValueError(
                    f"Task {t.id} depends on missing task {dep}"
                )

    in_degree: dict[int, int] = {t.id: len(t.depends_on) for t in dag.tasks}
    dependents: dict[int, list[int]] = defaultdict(list)
    for t in dag.tasks:
        for dep in t.depends_on:
            dependents[dep].append(t.id)

    current: list[Task] = sorted(
        (t for t in dag.tasks if in_degree[t.id] == 0),
        key=lambda t: t.id,
    )
    levels: list[list[Task]] = []
    processed = 0

    while current:
        levels.append(current)
        processed += len(current)
        next_level_ids: list[int] = []
        for t in current:
            for child_id in dependents[t.id]:
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    next_level_ids.append(child_id)
        current = sorted(
            (task_by_id[i] for i in next_level_ids), key=lambda t: t.id
        )

    if processed < len(dag.tasks):
        unprocessed = [t.id for t in dag.tasks if in_degree[t.id] > 0]
        raise ValueError(
            f"DAG contains a cycle (tasks unable to schedule: {unprocessed})"
        )

    return levels


# Matches "$task_<id>" optionally followed by ".<field>" where <field> can
# be a dotted path (e.g. "$task_2.results.0" → results[0]).
_PLACEHOLDER_RE = re.compile(r"^\$task_(\d+)(?:\.(.+))?$")


def _resolve_field_path(
    value: Any, path: str, task_id: int
) -> Any:
    """Follow a dotted path into ``value``. Integers select list indices."""
    for segment in path.split("."):
        if isinstance(value, dict):
            if segment not in value:
                raise ValueError(
                    f"Placeholder field {path!r} on task {task_id}: "
                    f"no key {segment!r}"
                )
            value = value[segment]
        elif isinstance(value, (list, tuple)):
            try:
                index = int(segment)
            except ValueError as exc:
                raise ValueError(
                    f"Placeholder field {path!r} on task {task_id}: "
                    f"cannot index list with {segment!r}"
                ) from exc
            if not -len(value) <= index < len(value):
                raise ValueError(
                    f"Placeholder field {path!r} on task {task_id}: "
                    f"index {index} out of range"
                )
            value = value[index]
        else:
            raise ValueError(
                f"Placeholder field {path!r} on task {task_id}: "
                f"cannot traverse into {type(value).__name__}"
            )
    return value


def substitute_placeholders(
    args: Any,
    prior_outputs: dict[int, Any],
) -> Any:
    """Recursively replace ``"$task_<id>"`` placeholders with prior outputs.

    Operates on nested dicts and lists. A placeholder is recognised only
    when it is the *entire* string value (no mid-string interpolation).

    Raises
    ------
    ValueError
        If a referenced task hasn't completed yet, or if a ``.field`` path
        cannot be resolved against the referenced output.
    """
    if isinstance(args, str):
        m = _PLACEHOLDER_RE.match(args)
        if m is None:
            return args
        task_id = int(m.group(1))
        field_path = m.group(2)
        if task_id not in prior_outputs:
            raise ValueError(
                f"Placeholder $task_{task_id} references a task that hasn't "
                f"completed yet"
            )
        value = prior_outputs[task_id]
        if field_path:
            value = _resolve_field_path(value, field_path, task_id)
        return value
    if isinstance(args, dict):
        return {k: substitute_placeholders(v, prior_outputs) for k, v in args.items()}
    if isinstance(args, list):
        return [substitute_placeholders(v, prior_outputs) for v in args]
    return args
