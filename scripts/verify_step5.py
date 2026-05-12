from __future__ import annotations

"""Verify Step 5 — the judge's semantic-equivalence behavior on 9 cases.

Cases:
  1. exact match                         → expect correct=True
  2. semantic match                      → expect correct=True
  3. format variation (#)                → expect correct=True
  4. name variation                      → expect correct=True
  5. wrong year                          → expect correct=False
  6. numeric hedge, exact value          → expect correct=True   (rule 7)
  7. numeric hedge, "about"              → expect correct=True   (rule 7)
  8. numeric hedge, close value          → expect correct=True   (rule 7)
  9. numeric hedge, far-off value        → expect correct=False  (rule 7)

Cases 6-9 cover the Step 6 Bonn bug regression: Wikipedia population /
quantity answers are inherently approximate, so a hedged prediction with
a reasonable cited number should grade correct, but the hedge does not
save a substantially-wrong number.

Prints each result. Prints PASS if all 9 verdicts match expectations,
FAIL otherwise.

Run:

    python scripts/verify_step5.py
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.judge import judge_answer  # noqa: E402
from src.llm.gemini import GeminiProvider  # noqa: E402


CASES: list[dict] = [
    {
        "label": "exact match",
        "question": "What is the capital of France?",
        "gold": "Paris",
        "predicted": "Paris",
        "expected": True,
    },
    {
        "label": "semantic match",
        "question": "What is the capital of France?",
        "gold": "Paris",
        "predicted": "The capital is Paris.",
        "expected": True,
    },
    {
        "label": "format variation (numeric)",
        "question": "What is the population of Bonn?",
        "gold": "300,000",
        "predicted": "three hundred thousand",
        "expected": True,
    },
    {
        "label": "name variation",
        "question": "Who discovered radium?",
        "gold": "Marie Curie",
        "predicted": "Maria Skłodowska-Curie",
        "expected": True,
    },
    {
        "label": "wrong year",
        "question": "When was Zhu (musician) born?",
        "gold": "1989",
        "predicted": "1990",
        "expected": False,
    },
    # ---- Numeric-tolerance cases (Bonn-bug regression) ---------------------
    {
        "label": "numeric hedge — exceeds (exact value)",
        "question": "What is the population of Bonn?",
        "gold": "300,000",
        "predicted": "exceeds 300,000",
        "expected": True,
    },
    {
        "label": "numeric hedge — about (exact value)",
        "question": "What is the population of Bonn?",
        "gold": "300,000",
        "predicted": "about 300,000",
        "expected": True,
    },
    {
        "label": "numeric hedge — close value (within ~25%)",
        "question": "What is the population of Bonn?",
        "gold": "300,000",
        "predicted": "around 250,000",
        "expected": True,
    },
    {
        "label": "numeric hedge — far-off value (hedge doesn't save it)",
        "question": "What is the population of Bonn?",
        "gold": "300,000",
        "predicted": "exceeds 500,000",
        "expected": False,
    },
]


async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set.")
        return 1

    llm = GeminiProvider()
    print(f"Judge model: {llm.model}")
    print(f"Running {len(CASES)} cases…\n")

    matches: list[bool] = []
    for i, case in enumerate(CASES, start=1):
        verdict = await judge_answer(
            question=case["question"],
            gold=case["gold"],
            predicted=case["predicted"],
            llm=llm,
        )
        actual = verdict.get("correct")
        ok = actual == case["expected"]
        matches.append(ok)

        tag = "OK" if ok else "MISMATCH"
        print(f"[{tag}] Case {i}: {case['label']}")
        print(f"        Q:         {case['question']}")
        print(f"        gold:      {case['gold']!r}")
        print(f"        predicted: {case['predicted']!r}")
        print(f"        expected:  {case['expected']}   actual: {actual}")
        print(f"        rationale: {verdict.get('rationale', '')!r}")
        print()

    overall = "PASS" if all(matches) else "FAIL"
    print(f"=== {overall}  ({sum(matches)}/{len(matches)} matched expectations) ===")
    return 0 if all(matches) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
