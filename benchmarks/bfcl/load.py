from __future__ import annotations

"""Load the BFCL v4 parallel-function subset and sample 30 tasks.

BFCL = Berkeley Function Calling Leaderboard. The ``parallel`` subset
contains tasks where the model must emit *multiple* function calls in
parallel from a single user prompt — exactly the pattern DAG-style
strategies should be best at.

Source files (raw JSONL, one task per line):

  https://raw.githubusercontent.com/ShishirPatil/gorilla/main/
    berkeley-function-call-leaderboard/bfcl_eval/data/
      BFCL_v4_parallel.json                       — tasks (question + functions)
      possible_answer/BFCL_v4_parallel.json       — ground truth (function calls)

Two BFCL conventions worth flagging:

* ``"type": "dict"`` in BFCL parameter schemas → we rewrite to
  ``"type": "object"`` to match JSON-Schema (which Gemini expects).
* Function names may contain dots (e.g. ``spotify.play``). Gemini's
  function-calling API rejects those; we substitute dots with
  underscores (``spotify_play``) and record the mapping so the AST judge
  can normalise predicted-call names the same way.

Run:

    python -m benchmarks.bfcl.load
    python -m benchmarks.bfcl.load --n 30 --seed 42
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

import httpx

RAW_BASE: str = (
    "https://raw.githubusercontent.com/ShishirPatil/gorilla/main/"
    "berkeley-function-call-leaderboard/bfcl_eval/data"
)

HERE: Path = Path(__file__).resolve().parent
RAW_DIR: Path = HERE / "raw"
RAW_TASKS: Path = RAW_DIR / "BFCL_v4_parallel.json"
RAW_ANSWERS: Path = RAW_DIR / "BFCL_v4_parallel_answers.json"
TASKS_PATH: Path = HERE / "tasks.json"

DEFAULT_N: int = 30
DEFAULT_SEED: int = 42

_DOT_NAME = re.compile(r"\.")


def _normalize_function_name(name: str) -> str:
    """Replace dots in function names with underscores so Gemini accepts them."""
    return _DOT_NAME.sub("_", name)


_TYPE_REMAP: dict[str, str] = {
    # BFCL uses BFCL-flavoured Python-ish type names; Gemini wants
    # standard JSON Schema types.
    "dict": "object",
    "tuple": "array",
    "float": "number",
    "double": "number",
    "long": "integer",
    "int": "integer",
    "bool": "boolean",
}


def _normalize_schema(node: Any) -> Any:
    """Walk a BFCL-style parameter schema, rewriting non-standard type
    names to JSON Schema types and stripping anything Gemini rejects."""
    if isinstance(node, dict):
        rewritten: dict[str, Any] = {}
        for k, v in node.items():
            if k == "type" and isinstance(v, str):
                if v == "any":
                    # BFCL "any" — Gemini doesn't accept it; drop type.
                    continue
                rewritten[k] = _TYPE_REMAP.get(v, v)
            else:
                rewritten[k] = _normalize_schema(v)
        return rewritten
    if isinstance(node, list):
        return [_normalize_schema(x) for x in node]
    return node


def _extract_user_prompt(question: Any) -> str:
    """BFCL stores ``question`` as ``[[{"role":"user","content":"..."}]]``
    (turn-list of message-list). Concatenate every user message."""
    if not isinstance(question, list):
        return str(question)
    parts: list[str] = []
    for turn in question:
        if not isinstance(turn, list):
            continue
        for msg in turn:
            if isinstance(msg, dict) and msg.get("role") == "user":
                parts.append(str(msg.get("content", "")))
    return "\n".join(p for p in parts if p)


def download_raw(force: bool = False) -> None:
    """Fetch both BFCL files into ``raw/`` if not already present."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for url_suffix, target in (
        ("BFCL_v4_parallel.json", RAW_TASKS),
        ("possible_answer/BFCL_v4_parallel.json", RAW_ANSWERS),
    ):
        if target.exists() and not force:
            print(f"Already present: {target} ({target.stat().st_size} bytes)")
            continue
        url = f"{RAW_BASE}/{url_suffix}"
        print(f"Downloading {url} → {target}")
        r = httpx.get(url, follow_redirects=True, timeout=60.0)
        r.raise_for_status()
        target.write_bytes(r.content)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def build_tasks(
    n: int = DEFAULT_N, seed: int = DEFAULT_SEED
) -> list[dict[str, Any]]:
    """Sample and normalize ``n`` BFCL parallel tasks (deterministic by seed)."""
    raw_tasks = _read_jsonl(RAW_TASKS)
    raw_answers = _read_jsonl(RAW_ANSWERS)
    answers_by_id = {a["id"]: a for a in raw_answers}

    rng = random.Random(seed)
    sampled = rng.sample(raw_tasks, min(n, len(raw_tasks)))

    out: list[dict[str, Any]] = []
    for t in sampled:
        tid = t["id"]
        user_prompt = _extract_user_prompt(t.get("question", []))

        # Normalize function schemas.
        functions: list[dict[str, Any]] = []
        for fn in t.get("function", []):
            name = _normalize_function_name(fn["name"])
            params = _normalize_schema(fn.get("parameters", {"type": "object"}))
            if not isinstance(params, dict):
                params = {"type": "object"}
            # Ensure top-level type is "object" — Gemini insists.
            if params.get("type") != "object":
                params["type"] = "object"
            functions.append(
                {
                    "name": name,
                    "description": fn.get("description", ""),
                    "parameters": params,
                    "_original_name": fn["name"],
                }
            )

        # Ground truth → ``gold_calls``. BFCL stores each call as a dict
        # ``{function_name: {arg: [acceptable_values, ...]}}``. We
        # flatten to ``[{"function_name": ..., "args": {arg: [acceptable_values]}}]``.
        gt = answers_by_id.get(tid, {}).get("ground_truth", [])
        gold_calls: list[dict[str, Any]] = []
        for call_entry in gt:
            if not isinstance(call_entry, dict) or len(call_entry) != 1:
                continue
            ((fn_name, args_dict),) = call_entry.items()
            normalised = _normalize_function_name(fn_name)
            gold_calls.append(
                {
                    "function_name": normalised,
                    "_original_function_name": fn_name,
                    "args": args_dict,  # values are lists of acceptable equivalents
                }
            )

        out.append(
            {
                "id": tid,
                "question": user_prompt,
                "functions": functions,
                "gold_calls": gold_calls,
                # Standard fields used elsewhere in our pipeline:
                "answer": json.dumps(gold_calls, ensure_ascii=False),
                "answer_type": "bfcl_calls",
                "category": "bfcl_parallel",
            }
        )
    return out


def save(tasks: list[dict[str, Any]], path: Path = TASKS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sample BFCL parallel tasks.")
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args(argv)

    download_raw(force=args.force_download)
    tasks = build_tasks(n=args.n, seed=args.seed)
    save(tasks)

    print(f"\nSampled {len(tasks)} BFCL parallel tasks (saved to {TASKS_PATH}).")
    print(f"Number of unique tools across the {len(tasks)} sampled tasks:")
    all_fns = {f["name"] for t in tasks for f in t["functions"]}
    print(f"  {len(all_fns)} distinct function names")
    print(f"\nFirst 3 sampled tasks:")
    for t in tasks[:3]:
        print(f"\n=== {t['id']} ===")
        print(f"  question: {t['question'][:160]}{'…' if len(t['question']) > 160 else ''}")
        print(f"  functions: {[f['name'] for f in t['functions']]}")
        print(f"  gold_calls: {len(t['gold_calls'])}")
        for gc in t["gold_calls"]:
            print(f"    - {gc['function_name']}({gc['args']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
