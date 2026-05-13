from __future__ import annotations

"""AST-style evaluator for BFCL parallel function-call tasks.

For BFCL, "correctness" means the strategy emitted the right *set* of
function calls with semantically-equivalent arguments — not a free-text
answer that an LLM judge would score. BFCL ships its ground truth as a
list of expected calls where each argument's value is a *list of
acceptable equivalents* (e.g. ``"location": ["Los Angeles", "LA",
"Los Angeles, CA"]``), capturing the synonyms a model might output.

This judge:

  1. Greedily bipartite-matches each gold call to an unused predicted
     call with the same (normalised) ``function_name`` and arguments
     that satisfy every gold-arg constraint.
  2. Marks the task **correct** iff every gold call found a match. Extra
     predicted calls beyond the gold set are allowed (BFCL's parallel
     subset deliberately permits over-emission).
  3. Compares argument values with BFCL-style equivalence:
       - Strings: case-insensitive after trimming whitespace.
       - Numerics: absolute tolerance ``1e-5`` OR relative ``0.1%``,
         whichever is larger. ``True``/``False`` count as 1/0.
       - Lists: order-insensitive recursive match (acceptable for
         BFCL where call args sometimes hold list values like
         ``["alice", "bob"]``).
       - A predicted value passes if it equals *any* element in the
         gold's acceptable-equivalents list.

Returns ``{"correct": bool, "rationale": str}`` — same shape as the
LLM judge so :mod:`src.run_eval` can plug either in.
"""

from typing import Any


# ---------------------------------------------------------------------------
# Value equivalence
# ---------------------------------------------------------------------------
_NUMERIC_ABS_TOL: float = 1e-5
_NUMERIC_REL_TOL: float = 1e-3


def _is_numeric(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _numeric_value(x: Any) -> float:
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    return float(x)


def _normalize_string(s: str) -> str:
    return s.strip().lower()


def _values_equivalent(a: Any, b: Any) -> bool:
    """One-on-one equivalence with BFCL-style tolerance rules."""
    # Bools are checked first because ``bool`` is a subclass of ``int``.
    if isinstance(a, bool) or isinstance(b, bool):
        return _numeric_value(a) == _numeric_value(b) if (
            (_is_numeric(a) or isinstance(a, bool))
            and (_is_numeric(b) or isinstance(b, bool))
        ) else a == b
    if _is_numeric(a) and _is_numeric(b):
        fa, fb = _numeric_value(a), _numeric_value(b)
        return abs(fa - fb) <= max(_NUMERIC_ABS_TOL, abs(fb) * _NUMERIC_REL_TOL)
    if isinstance(a, str) and isinstance(b, str):
        return _normalize_string(a) == _normalize_string(b)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        used = [False] * len(b)
        for x in a:
            matched = False
            for i, y in enumerate(b):
                if not used[i] and _values_equivalent(x, y):
                    used[i] = True
                    matched = True
                    break
            if not matched:
                return False
        return True
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_values_equivalent(a[k], b[k]) for k in a)
    # Fall back to exact equality.
    return a == b


def _predicted_value_in_acceptable(
    predicted: Any, acceptable: Any
) -> bool:
    """BFCL gold args carry a LIST of acceptable equivalents per arg.

    Predicted value passes if it matches any of them. We also accept the
    pathological case where ``acceptable`` is a scalar (some BFCL rows
    aren't list-wrapped); treat it as a single-element list.
    """
    if isinstance(acceptable, list):
        candidates = acceptable
    else:
        candidates = [acceptable]
    for candidate in candidates:
        if _values_equivalent(predicted, candidate):
            return True
    return False


# ---------------------------------------------------------------------------
# Function-call matching
# ---------------------------------------------------------------------------
def _args_satisfy_gold(
    predicted_args: dict[str, Any], gold_args: dict[str, Any]
) -> bool:
    """Every gold argument key must be present in predicted args with a
    value matching one of the gold's acceptable equivalents. Extra
    predicted args beyond the gold's set are allowed."""
    for arg_name, acceptable in gold_args.items():
        if arg_name not in predicted_args:
            return False
        if not _predicted_value_in_acceptable(predicted_args[arg_name], acceptable):
            return False
    return True


def evaluate_bfcl(
    predicted_calls: list[dict[str, Any]],
    gold_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return ``{"correct": bool, "rationale": str}``.

    ``predicted_calls`` is a list of ``{"function_name": str, "args": dict}``
    in the order the strategy emitted them. ``gold_calls`` is the same
    shape with arg values being lists of acceptable equivalents.

    Algorithm: greedily match each gold call to an unused predicted call
    by name + args. The order doesn't matter for parallel BFCL — a model
    can emit calls in any order.
    """
    if not gold_calls:
        return {"correct": False, "rationale": "no gold calls supplied"}

    used: list[bool] = [False] * len(predicted_calls)
    missing: list[dict[str, Any]] = []

    for gold in gold_calls:
        gold_name = gold["function_name"]
        gold_args = gold.get("args", {})
        matched_index: int = -1
        for i, pred in enumerate(predicted_calls):
            if used[i]:
                continue
            if pred.get("function_name") != gold_name:
                continue
            if not _args_satisfy_gold(pred.get("args", {}), gold_args):
                continue
            matched_index = i
            break
        if matched_index < 0:
            missing.append(gold)
        else:
            used[matched_index] = True

    if not missing:
        n_extra = sum(1 for u in used if not u)
        rationale = (
            f"All {len(gold_calls)} gold call(s) matched."
            + (f" {n_extra} extra predicted call(s) — allowed for parallel BFCL." if n_extra else "")
        )
        return {"correct": True, "rationale": rationale}

    # Build a concise rationale on the first 3 misses.
    miss_summaries = []
    for gold in missing[:3]:
        miss_summaries.append(
            f"{gold['function_name']}({gold.get('args')})"
        )
    rationale = (
        f"Missing {len(missing)}/{len(gold_calls)} gold call(s). "
        f"Unmatched: {miss_summaries}. "
        f"Predicted: {[p.get('function_name') for p in predicted_calls]}."
    )
    return {"correct": False, "rationale": rationale}
