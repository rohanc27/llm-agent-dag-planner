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
reasonable upgrade for the final eval — flagged for Weekend 3.

See SPEC.md § 3 Step 5.
"""

import json
import re
from typing import Any, Optional

from src.llm.base import LLMProvider
from src.llm.gemini import extract_text

# Hard cap on judge output — verdict + one sentence rationale is tiny.
_JUDGE_MAX_TOKENS: int = 512

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
)


def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    """Return the first balanced ``{...}`` JSON object in ``text``, or None.

    Tolerates leading/trailing prose and fenced code blocks.
    """
    s = text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*\n(.*)\n```\s*$", s, flags=re.DOTALL)
    if fence:
        s = fence.group(1).strip()

    # Fast path: the whole string is the JSON object.
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Otherwise scan for the first balanced ``{...}``.
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = s[start : i + 1]
                try:
                    obj = json.loads(candidate)
                except json.JSONDecodeError:
                    return None
                return obj if isinstance(obj, dict) else None
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
) -> dict[str, Any]:
    """Grade ``predicted`` against ``gold`` for ``question``.

    Returns ``{"correct": bool, "rationale": str}``.

    On a parse failure, retries once with a stricter user-side instruction.
    If both attempts fail, returns ``{"correct": False, "rationale":
    "JUDGE_PARSE_ERROR: <raw>"}`` so the failure is visible in the eval
    rather than silently dropped.
    """
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
            system=JUDGE_SYSTEM_PROMPT,
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
