from __future__ import annotations

"""Unit tests for src/core/dag.py.

Run with:

    pytest tests/test_dag.py -v
"""

import pytest

from src.core.dag import (
    DAG,
    Task,
    substitute_placeholders,
    topological_levels,
)


def _ids(levels: list[list[Task]]) -> list[list[int]]:
    return [[t.id for t in lvl] for lvl in levels]


# ---------------------------------------------------------------------------
# topological_levels
# ---------------------------------------------------------------------------
def test_linear_chain() -> None:
    dag = DAG(
        tasks=[
            Task(id=0, tool="x", args={}, depends_on=[]),
            Task(id=1, tool="x", args={}, depends_on=[0]),
            Task(id=2, tool="x", args={}, depends_on=[1]),
        ]
    )
    assert _ids(topological_levels(dag)) == [[0], [1], [2]]


def test_fan_out() -> None:
    dag = DAG(
        tasks=[
            Task(id=0, tool="x", args={}, depends_on=[]),
            Task(id=1, tool="x", args={}, depends_on=[0]),
            Task(id=2, tool="x", args={}, depends_on=[0]),
        ]
    )
    assert _ids(topological_levels(dag)) == [[0], [1, 2]]


def test_fan_in() -> None:
    dag = DAG(
        tasks=[
            Task(id=0, tool="x", args={}, depends_on=[]),
            Task(id=1, tool="x", args={}, depends_on=[]),
            Task(id=2, tool="x", args={}, depends_on=[0, 1]),
        ]
    )
    assert _ids(topological_levels(dag)) == [[0, 1], [2]]


def test_diamond() -> None:
    dag = DAG(
        tasks=[
            Task(id=0, tool="x", args={}, depends_on=[]),
            Task(id=1, tool="x", args={}, depends_on=[0]),
            Task(id=2, tool="x", args={}, depends_on=[0]),
            Task(id=3, tool="x", args={}, depends_on=[1, 2]),
        ]
    )
    assert _ids(topological_levels(dag)) == [[0], [1, 2], [3]]


def test_independent_parallel() -> None:
    dag = DAG(
        tasks=[
            Task(id=0, tool="x", args={}, depends_on=[]),
            Task(id=1, tool="x", args={}, depends_on=[]),
            Task(id=2, tool="x", args={}, depends_on=[]),
        ]
    )
    assert _ids(topological_levels(dag)) == [[0, 1, 2]]


def test_levels_are_sorted_by_id() -> None:
    # If we insert tasks in non-id order, levels still emit ascending ids.
    dag = DAG(
        tasks=[
            Task(id=2, tool="x", args={}, depends_on=[0]),
            Task(id=0, tool="x", args={}, depends_on=[]),
            Task(id=1, tool="x", args={}, depends_on=[0]),
        ]
    )
    assert _ids(topological_levels(dag)) == [[0], [1, 2]]


def test_cycle_raises() -> None:
    dag = DAG(
        tasks=[
            Task(id=0, tool="x", args={}, depends_on=[1]),
            Task(id=1, tool="x", args={}, depends_on=[0]),
        ]
    )
    with pytest.raises(ValueError, match="cycle"):
        topological_levels(dag)


def test_self_loop_raises() -> None:
    dag = DAG(tasks=[Task(id=0, tool="x", args={}, depends_on=[0])])
    with pytest.raises(ValueError, match="cycle"):
        topological_levels(dag)


def test_missing_dependency_raises() -> None:
    dag = DAG(tasks=[Task(id=0, tool="x", args={}, depends_on=[99])])
    with pytest.raises(ValueError, match="missing task 99"):
        topological_levels(dag)


def test_duplicate_id_raises() -> None:
    dag = DAG(
        tasks=[
            Task(id=0, tool="x", args={}, depends_on=[]),
            Task(id=0, tool="x", args={}, depends_on=[]),
        ]
    )
    with pytest.raises(ValueError, match="Duplicate"):
        topological_levels(dag)


# ---------------------------------------------------------------------------
# substitute_placeholders
# ---------------------------------------------------------------------------
def test_substitute_simple_reference() -> None:
    args = {"q": "$task_0"}
    out = substitute_placeholders(args, {0: "hello"})
    assert out == {"q": "hello"}


def test_substitute_keeps_non_placeholders_unchanged() -> None:
    args = {"q": "plain string", "n": 42, "ok": True}
    assert substitute_placeholders(args, {}) == args


def test_substitute_dict_field_path() -> None:
    args = {"q": "$task_0.title"}
    out = substitute_placeholders(args, {0: {"title": "Eiffel", "year": 1889}})
    assert out == {"q": "Eiffel"}


def test_substitute_list_index() -> None:
    args = {"q": "$task_0.0"}
    out = substitute_placeholders(args, {0: ["first", "second"]})
    assert out == {"q": "first"}


def test_substitute_nested_path() -> None:
    args = {"q": "$task_0.results.0.title"}
    out = substitute_placeholders(
        args, {0: {"results": [{"title": "x"}, {"title": "y"}]}}
    )
    assert out == {"q": "x"}


def test_substitute_inside_nested_dict() -> None:
    args = {"outer": {"inner": "$task_0"}}
    out = substitute_placeholders(args, {0: "X"})
    assert out == {"outer": {"inner": "X"}}


def test_substitute_inside_list() -> None:
    args = {"items": ["plain", "$task_0", "$task_1"]}
    out = substitute_placeholders(args, {0: "A", 1: "B"})
    assert out == {"items": ["plain", "A", "B"]}


def test_substitute_replaces_entire_string_only() -> None:
    # Mid-string interpolation is NOT supported — the placeholder is only
    # recognised when it is the whole value.
    args = {"q": "look up $task_0 carefully"}
    out = substitute_placeholders(args, {0: "X"})
    assert out == {"q": "look up $task_0 carefully"}


def test_substitute_missing_task_raises() -> None:
    args = {"q": "$task_5"}
    with pytest.raises(ValueError, match="task that hasn't"):
        substitute_placeholders(args, {0: "x"})


def test_substitute_missing_field_raises() -> None:
    args = {"q": "$task_0.missing"}
    with pytest.raises(ValueError, match="no key 'missing'"):
        substitute_placeholders(args, {0: {"present": "x"}})


def test_substitute_list_index_out_of_range_raises() -> None:
    args = {"q": "$task_0.5"}
    with pytest.raises(ValueError, match="out of range"):
        substitute_placeholders(args, {0: ["a", "b"]})


def test_substitute_traverse_into_scalar_raises() -> None:
    args = {"q": "$task_0.field"}
    with pytest.raises(ValueError, match="cannot traverse"):
        substitute_placeholders(args, {0: 42})
