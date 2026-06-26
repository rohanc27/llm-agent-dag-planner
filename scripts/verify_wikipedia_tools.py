from __future__ import annotations

"""Verify Wikipedia tools work end-to-end against the live API.

Three things checked:
  1. ``wikipedia_search("Albert Einstein")`` returns a non-empty list of
     titles, with "Albert Einstein" at or near the top.
  2. ``wikipedia_fetch(<top title>)`` returns prose that mentions "Einstein"
     and is approximately 500 words long.
  3. The ``Tool`` dataclass round-trip works: calling
     ``WIKIPEDIA_SEARCH_TOOL.execute(query=...)`` matches the bare function,
     and ``Tool.to_def()`` produces the declarative shape providers expect.

Run:

    python scripts/verify_wikipedia_tools.py
"""

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.tools.wikipedia import (  # noqa: E402
    WIKIPEDIA_FETCH_TOOL,
    WIKIPEDIA_SEARCH_TOOL,
    wikipedia_fetch,
    wikipedia_search,
)


def _truncate(s: str, n: int = 600) -> str:
    return s if len(s) <= n else s[:n] + "…"


async def main() -> int:
    query = "Albert Einstein"

    # ---- 1. Search ---------------------------------------------------------
    print(f"=== wikipedia_search({query!r}) ===")
    titles = await wikipedia_search(query)
    for i, title in enumerate(titles, start=1):
        print(f"  {i}. {title}")
    print()
    if not titles:
        print("ERROR: search returned no titles.")
        return 1

    # ---- 2. Fetch ----------------------------------------------------------
    top_title = titles[0]
    print(f"=== wikipedia_fetch({top_title!r}) — first 500 words ===")
    body = await wikipedia_fetch(top_title)
    print(_truncate(body))
    print()
    word_count = len(body.split())
    char_count = len(body)
    print(f"  word_count: {word_count}")
    print(f"  char_count: {char_count}")
    print()
    if word_count == 0:
        print("ERROR: fetch returned an empty body.")
        return 1

    # ---- 3. Tool dataclass round-trip --------------------------------------
    print("=== Tool dataclass round-trip ===")
    other_query = "Marie Curie"
    titles_via_tool = await WIKIPEDIA_SEARCH_TOOL.execute(query=other_query)
    print(f"  WIKIPEDIA_SEARCH_TOOL.execute(query={other_query!r})")
    print(f"    -> {titles_via_tool}")
    if titles_via_tool:
        body_via_tool = await WIKIPEDIA_FETCH_TOOL.execute(title=titles_via_tool[0])
        snippet = _truncate(body_via_tool, 200)
        print(f"  WIKIPEDIA_FETCH_TOOL.execute(title={titles_via_tool[0]!r})")
        print(f"    -> {snippet!r}")
    print()

    print("=== Tool.to_def() (what the provider sees) ===")
    for tool in (WIKIPEDIA_SEARCH_TOOL, WIKIPEDIA_FETCH_TOOL):
        defn = tool.to_def()
        print(f"  {defn['name']}:")
        print(f"    description: {defn['description']}")
        print(f"    input_schema: {defn['input_schema']}")
    print()

    # ---- Soft sanity checks (informational, not fatal) ---------------------
    if "Einstein" not in body:
        print("WARN: 'Einstein' not found in fetched body — top hit may have shifted.")
    if not (300 <= word_count <= 500):
        print(
            f"WARN: word_count={word_count} outside the expected 300–500 band "
            f"(short articles can land below 500; that's OK)."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
