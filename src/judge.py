from __future__ import annotations

"""LLM-as-judge for HotpotQA answer correctness.

A single async :func:`judge_answer` calls Gemini 2.5 Flash with no tools and
asks it to emit a JSON verdict. We deliberately use plain text + JSON parsing
rather than tool-calling: it keeps the judge simple, sidesteps any
``tool_config`` conflicts inside the eval loop, and is easy to debug.

The HotpotQA answers are short spans, so the prompt emphasizes semantic
equivalence (formatting / name / phrasing variation = correct) while still
penalizing factual errors.

A separate, higher-quality judge model (e.g. Gemini 2.5 Pro) would be a
reasonable upgrade for the final eval — flagged for later iteration.


"""

import ast
import json
import re
from typing import Any, Optional

from src.llm.base import LLMProvider
from src.llm.gemini import extract_text

# Hard cap on judge output. Bumped from 512 → 1024 after a an earlier truncation
# regression: a verbose rationale was being cut mid-string, leaving an
# unparseable JSON tail. One sentence is still the target — this is headroom.
_JUDGE_MAX_TOKENS: int = 1024

JUDGE_SYSTEM_PROMPT: str = (
    "You are a strict grader for HotpotQA short-answer questions. Given a "
    "QUESTION, a GOLD answer, and a PREDICTED answer, decide whether the "
    "predicted answer is correct.\n"
    "\n"
    "Output format (mandatory):\n"
    '  Respond with EXACTLY one JSON object: {"correct": true|false, "rationale": "<one sentence>"}\n'
    "  No prose before or after the JSON. No markdown code fences.\n"
    "\n"
    "Grading rules:\n"
    "  1. Factual accuracy is non-negotiable. Wrong facts are NEVER correct "
    "(e.g. gold '1989' vs predicted '1990' → wrong).\n"
    "  2. Accept semantic equivalence: a prediction that contains or paraphrases "
    "the gold answer counts as correct (e.g. gold 'Paris' vs predicted 'The "
    "capital is Paris.' → correct).\n"
    "  3. Accept formatting variants of numeric / date answers (e.g. '300,000' "
    "vs '300000' vs 'three hundred thousand' → correct).\n"
    "  4. Accept name variants — alternate transliterations, full vs partial "
    "names, married vs maiden names (e.g. 'Marie Curie' vs 'Maria "
    "Skłodowska-Curie' → correct).\n"
    "  5. A prediction that supplies only one part of a multi-part gold answer "
    "is wrong (e.g. gold 'Paris, France' vs predicted 'France' → wrong).\n"
    "  6. Hedged or ambiguous predictions that mention both the right and a "
    "wrong answer are wrong.\n"
    "  7. Wikipedia quantity figures (populations, sizes, counts) are inherently "
    "approximate. For numeric answers, when the prediction uses approximation "
    "language ('exceeds', 'over', 'about', 'approximately', 'roughly', "
    "'around', 'more than', 'nearly') AND the cited number is within roughly "
    "25% of the gold, mark correct (e.g. gold '300,000' vs predicted 'exceeds "
    "300,000' or 'around 250,000' → correct). If the prediction cites a number "
    "substantially different from the gold (e.g. gold '300,000' vs predicted "
    "'exceeds 500,000'), the hedge does NOT save it — mark wrong.\n"
)


# -----------------------------------------------------------------------------
# Per-answer-type emphasis appended to the system prompt for the GitHub
# benchmark. None of these override the base rules above — they tighten or
# loosen scoring along the dimensions documented in the SPEC for 
# -----------------------------------------------------------------------------
_ANSWER_TYPE_HINTS: dict[str, str] = {
    "count": (
        "ANSWER TYPE: count (numeric).\n"
        "Treat the gold as a number. Accept predictions within ±10% "
        "tolerance — for example, gold '85' accepts any prediction in "
        "the range [76, 94]. Approximation language ('around', 'about', "
        "'roughly', 'exceeds', 'over', 'more than', 'nearly') around the "
        "cited number is acceptable as long as the cited number itself is "
        "within tolerance. Numbers substantially outside ±10% are wrong "
        "regardless of hedging."
    ),
    "name": (
        "ANSWER TYPE: name (single entity / value).\n"
        "Apply the standard semantic-equivalence and name-variant rules. "
        "A prediction that contains the gold name (possibly with extra "
        "phrasing around it) is correct."
    ),
    "list": (
        "ANSWER TYPE: list (set-match semantics).\n"
        "The gold is a list of items, often as 'key: value' pairs. Mark "
        "correct when EVERY gold item appears somewhere in the prediction "
        "with its associated value matching (case-insensitive for typical "
        "names / languages). Order does NOT matter. Extra items or extra "
        "phrasing in the prediction are fine unless they directly "
        "contradict a gold item. Missing any required item is wrong."
    ),
    "comparison": (
        "ANSWER TYPE: comparison (winner of a comparison).\n"
        "The gold names the entity that wins the comparison. Mark correct "
        "if the prediction unambiguously identifies the SAME winner — "
        "even if it adds reasoning, numbers, or supporting context around "
        "the answer. If the prediction names a different winner, or hedges "
        "between two candidates, mark wrong."
    ),
}


def _build_judge_system_prompt(answer_type: Optional[str]) -> str:
    """Return the base prompt, optionally with an answer-type addendum."""
    hint = _ANSWER_TYPE_HINTS.get(answer_type) if answer_type else None
    if hint is None:
        return JUDGE_SYSTEM_PROMPT
    return f"{JUDGE_SYSTEM_PROMPT}\n{hint}\n"


def _first_balanced_object(s: str) -> Optional[str]:
    """Return the first balanced ``{...}`` substring, or ``None``.

    Tracks both ``"`` and ``'`` as string delimiters so a ``}`` inside a
    Python-style single-quoted value doesn't trip up depth tracking.
    """
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    str_quote: Optional[str] = None
    escape = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == str_quote:
                in_str = False
                str_quote = None
            continue
        if c == '"' or c == "'":
            in_str = True
            str_quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    """Return the first balanced ``{...}`` object in ``text``, or None.

    Parse path:
      1. ``json.loads`` on the whole (fence-stripped) string.
      2. Brace-scan for the first balanced ``{...}`` and try ``json.loads``
         on the candidate.
      3. ``ast.literal_eval`` fallback on the candidate. Handles Python-
         style dicts (single-quote keys, ``True``/``False``/``None``,
         escaped single quotes inside values) — output shapes we've
         observed Gemini emit when it copies Python repr patterns instead
         of JSON.

    The ``judge_answer`` caller wraps this in a stricter-prompt retry as
    the next escalation, and falls back to ``JUDGE_PARSE_ERROR`` only when
    every path has failed.
    """
    s = text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*\n(.*)\n```\s*$", s, flags=re.DOTALL)
    if fence:
        s = fence.group(1).strip()

    # 1. Whole-string ``json.loads``.
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2. Brace scanner → ``json.loads`` on the first balanced ``{...}``.
    candidate = _first_balanced_object(s)
    if candidate is None:
        return None
    try:
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 3. ``ast.literal_eval`` fallback for Python-style output.
    try:
        obj = ast.literal_eval(candidate)
        if isinstance(obj, dict):
            return obj
    except (ValueError, SyntaxError):
        pass

    return None


def _coerce_verdict(obj: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Validate / lightly coerce the judge's JSON into ``{correct, rationale}``."""
    if "correct" not in obj:
        return None
    correct = obj["correct"]
    if isinstance(correct, str):
        token = correct.strip().lower()
        if token in {"true", "yes", "correct"}:
            correct = True
        elif token in {"false", "no", "incorrect", "wrong"}:
            correct = False
        else:
            return None
    if not isinstance(correct, bool):
        return None
    rationale = obj.get("rationale", "")
    if not isinstance(rationale, str):
        rationale = str(rationale)
    return {"correct": correct, "rationale": rationale}


def _user_message(question: str, gold: str, predicted: str, strict: bool = False) -> str:
    body = (
        f"QUESTION: {question}\n"
        f"GOLD: {gold}\n"
        f"PREDICTED: {predicted}\n"
    )
    if strict:
        body += (
            "\nReturn ONLY the JSON object — no markdown, no code fences, "
            "no commentary, no leading or trailing text.\n"
        )
    return body


async def judge_answer(
    question: str,
    gold: str,
    predicted: str,
    llm: LLMProvider,
    answer_type: Optional[str] = None,
) -> dict[str, Any]:
    """Grade ``predicted`` against ``gold`` for ``question``.

    Returns ``{"correct": bool, "rationale": str}``.

    ``answer_type`` (optional): when set to one of ``"count" | "name" |
    "list" | "comparison"`` (the GitHub benchmark's per-task annotation),
    a type-specific rule emphasis is appended to the system prompt.
    Default ``None`` preserves the original HotpotQA-shaped behavior.

    On a parse failure, retries once with a stricter user-side instruction.
    If both attempts fail, returns ``{"correct": False, "rationale":
    "JUDGE_PARSE_ERROR: <raw>"}`` so the failure is visible in the eval
    rather than silently dropped.
    """
    system_prompt = _build_judge_system_prompt(answer_type)
    raw_text: str = ""
    for attempt in range(2):
        response, _ = await llm.call(
            messages=[
                {
                    "role": "user",
                    "content": _user_message(
                        question, gold, predicted, strict=(attempt > 0)
                    ),
                }
            ],
            system=system_prompt,
            max_tokens=_JUDGE_MAX_TOKENS,
        )
        raw_text = extract_text(response)
        parsed = _extract_json_object(raw_text)
        if parsed is not None:
            verdict = _coerce_verdict(parsed)
            if verdict is not None:
                return verdict

    return {
        "correct": False,
        "rationale": f"JUDGE_PARSE_ERROR: {raw_text!r}",
    }
