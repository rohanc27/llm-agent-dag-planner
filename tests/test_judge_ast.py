from __future__ import annotations

"""Unit tests for the BFCL AST judge in :mod:`src.judge_ast`.

Covers:
  1. Exact match → correct.
  2. Missing gold call → wrong.
  3. Wrong arg value → wrong.
  4. Extra predicted calls beyond gold → correct (BFCL allows extras).
  5. Numeric tolerance (small float drift) → correct.
  6. Multiple acceptable string equivalents → correct.
  7. Order independence: gold calls in any order → correct.
"""

from src.judge_ast import evaluate_bfcl


def test_exact_match() -> None:
    verdict = evaluate_bfcl(
        predicted_calls=[
            {"function_name": "spotify_play", "args": {"artist": "Taylor Swift", "duration": 20}},
            {"function_name": "spotify_play", "args": {"artist": "Maroon 5", "duration": 15}},
        ],
        gold_calls=[
            {"function_name": "spotify_play", "args": {"artist": ["Taylor Swift"], "duration": [20]}},
            {"function_name": "spotify_play", "args": {"artist": ["Maroon 5"], "duration": [15]}},
        ],
    )
    assert verdict["correct"] is True


def test_missing_call_fails() -> None:
    verdict = evaluate_bfcl(
        predicted_calls=[
            {"function_name": "spotify_play", "args": {"artist": "Taylor Swift", "duration": 20}},
        ],
        gold_calls=[
            {"function_name": "spotify_play", "args": {"artist": ["Taylor Swift"], "duration": [20]}},
            {"function_name": "spotify_play", "args": {"artist": ["Maroon 5"], "duration": [15]}},
        ],
    )
    assert verdict["correct"] is False
    assert "Missing 1" in verdict["rationale"]


def test_wrong_arg_value_fails() -> None:
    verdict = evaluate_bfcl(
        predicted_calls=[
            {"function_name": "spotify_play", "args": {"artist": "Taylor Swift", "duration": 99}},
        ],
        gold_calls=[
            {"function_name": "spotify_play", "args": {"artist": ["Taylor Swift"], "duration": [20]}},
        ],
    )
    assert verdict["correct"] is False


def test_extra_predicted_calls_ok() -> None:
    """BFCL's parallel subset allows the strategy to emit extra calls
    beyond the gold set as long as every gold call is covered."""
    verdict = evaluate_bfcl(
        predicted_calls=[
            {"function_name": "spotify_play", "args": {"artist": "Taylor Swift", "duration": 20}},
            {"function_name": "spotify_play", "args": {"artist": "Maroon 5", "duration": 15}},
            {"function_name": "spotify_play", "args": {"artist": "Drake", "duration": 10}},  # extra
        ],
        gold_calls=[
            {"function_name": "spotify_play", "args": {"artist": ["Taylor Swift"], "duration": [20]}},
            {"function_name": "spotify_play", "args": {"artist": ["Maroon 5"], "duration": [15]}},
        ],
    )
    assert verdict["correct"] is True
    assert "extra" in verdict["rationale"].lower()


def test_numeric_tolerance() -> None:
    """Float drift within tolerance should pass — strategies sometimes
    emit 30.450001 where the gold expects 30.45."""
    verdict = evaluate_bfcl(
        predicted_calls=[
            {"function_name": "calc_sales_tax", "args": {"amount": 30.450001, "rate": 0.0825}},
        ],
        gold_calls=[
            {"function_name": "calc_sales_tax", "args": {"amount": [30.45], "rate": [0.0825]}},
        ],
    )
    assert verdict["correct"] is True


def test_multiple_acceptable_string_equivalents() -> None:
    """When gold provides multiple acceptable strings (e.g. 'LA' or
    'Los Angeles'), any match should pass."""
    verdict = evaluate_bfcl(
        predicted_calls=[
            {"function_name": "get_weather", "args": {"location": "LA", "hours": 3}},
        ],
        gold_calls=[
            {
                "function_name": "get_weather",
                "args": {
                    "location": ["Los Angeles", "LA", "Los Angeles, CA"],
                    "hours": [3],
                },
            },
        ],
    )
    assert verdict["correct"] is True


def test_gold_calls_in_any_order() -> None:
    """The matcher is order-insensitive — gold and predicted can be in
    different orders."""
    verdict = evaluate_bfcl(
        predicted_calls=[
            {"function_name": "spotify_play", "args": {"artist": "Maroon 5", "duration": 15}},
            {"function_name": "spotify_play", "args": {"artist": "Taylor Swift", "duration": 20}},
        ],
        gold_calls=[
            {"function_name": "spotify_play", "args": {"artist": ["Taylor Swift"], "duration": [20]}},
            {"function_name": "spotify_play", "args": {"artist": ["Maroon 5"], "duration": [15]}},
        ],
    )
    assert verdict["correct"] is True


def test_case_insensitive_string_match() -> None:
    """String values are compared case-insensitively after trimming."""
    verdict = evaluate_bfcl(
        predicted_calls=[
            {"function_name": "search", "args": {"query": "  PYTHON LANGUAGE  "}},
        ],
        gold_calls=[
            {"function_name": "search", "args": {"query": ["python language"]}},
        ],
    )
    assert verdict["correct"] is True
