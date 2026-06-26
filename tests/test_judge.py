from __future__ import annotations

"""Unit tests for src/judge.py JSON-extraction logic.

Run with:

    pytest tests/test_judge.py -v
"""

from src.judge import _extract_json_object, _first_balanced_object


def test_plain_json() -> None:
    raw = '{"correct": true, "rationale": "Exact match."}'
    assert _extract_json_object(raw) == {"correct": True, "rationale": "Exact match."}


def test_json_with_surrounding_prose() -> None:
    raw = 'Here is my verdict:\n{"correct": false, "rationale": "Wrong."}\nDone.'
    assert _extract_json_object(raw) == {"correct": False, "rationale": "Wrong."}


def test_markdown_fenced_json() -> None:
    raw = '```json\n{"correct": true, "rationale": "ok"}\n```'
    assert _extract_json_object(raw) == {"correct": True, "rationale": "ok"}


def test_python_style_dict_with_escaped_quote() -> None:
    """Regression for the Bonn judge bug.

    The model emitted Python-repr-style output containing an escaped
    single quote inside the rationale (``\\'exceeds\\'``). ``json.loads``
    can't handle Python-style strings; ``ast.literal_eval`` can.
    """
    raw = (
        "{'correct': False, 'rationale': "
        "'The population \\'exceeds\\' 300,000 — matches.'}"
    )
    result = _extract_json_object(raw)
    assert result is not None
    assert result["correct"] is False
    assert "exceeds" in result["rationale"]


def test_python_style_dict_double_quotes_inside() -> None:
    raw = "{'correct': True, 'rationale': \"Paris is the capital.\"}"
    assert _extract_json_object(raw) == {
        "correct": True,
        "rationale": "Paris is the capital.",
    }


def test_json_with_braces_inside_string_value() -> None:
    """The brace scanner must not exit early on a ``}`` inside a JSON string."""
    raw = '{"correct": true, "rationale": "Test {with braces} inside."}'
    assert _extract_json_object(raw) == {
        "correct": True,
        "rationale": "Test {with braces} inside.",
    }


def test_python_style_with_close_brace_inside_string() -> None:
    """Same scenario for Python-style — needs both quote types tracked."""
    raw = "{'correct': True, 'rationale': 'Has } in it.'}"
    assert _extract_json_object(raw) == {
        "correct": True,
        "rationale": "Has } in it.",
    }


def test_no_json_returns_none() -> None:
    assert _extract_json_object("totally not a json object") is None


def test_first_balanced_object_handles_both_quote_types() -> None:
    """The scanner returns the first complete object only."""
    raw = '{"a": 1} {"b": 2}'
    assert _first_balanced_object(raw) == '{"a": 1}'

    raw = "{'a': 1} {'b': 2}"
    assert _first_balanced_object(raw) == "{'a': 1}"
