from __future__ import annotations

"""Wikipedia search + fetch tools (HotpotQA evidence retrieval).

Two async functions plus their :class:`~src.tools.base.Tool` wrappers:

* :func:`wikipedia_search` — top-5 article titles for a query.
* :func:`wikipedia_fetch`  — first 500 words of an article's plain text body.

Both hit the public MediaWiki action API at
``https://en.wikipedia.org/w/api.php`` (no auth required). Per Wikimedia's
User-Agent policy we identify ourselves on every request. See SPEC.md § 3

"""

from typing import Any

import httpx

from src.tools.base import Tool

WIKIPEDIA_API: str = "https://en.wikipedia.org/w/api.php"
USER_AGENT: str = "llm-agent-dag-planner/0.1 (rohanc@gmail.com)"

# Conservative default for the public MediaWiki endpoint. Strategies that
# need a different bound should call the underlying API directly.
_DEFAULT_TIMEOUT: float = 20.0

_DEFAULT_MAX_WORDS: int = 500


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT}


async def wikipedia_search(query: str) -> list[str]:
    """Return the top-5 English Wikipedia article titles for ``query``.

    Empty list if the API returns no hits.
    """
    params: dict[str, Any] = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 5,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, headers=_headers()) as client:
        response = await client.get(WIKIPEDIA_API, params=params)
        response.raise_for_status()
        data = response.json()
    hits = data.get("query", {}).get("search", []) or []
    return [hit["title"] for hit in hits if "title" in hit]


async def wikipedia_fetch(title: str) -> str:
    """Return the first 500 words of the plain-text body for ``title``.

    Follows redirects. Returns an empty string if the title is missing or
    has no extract.
    """
    params: dict[str, Any] = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "redirects": 1,
        "titles": title,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, headers=_headers()) as client:
        response = await client.get(WIKIPEDIA_API, params=params)
        response.raise_for_status()
        data = response.json()
    pages = data.get("query", {}).get("pages", {}) or {}
    if not pages:
        return ""
    # Single-title queries return exactly one page entry; take it.
    page = next(iter(pages.values()))
    extract = page.get("extract", "") or ""
    words = extract.split()
    return " ".join(words[:_DEFAULT_MAX_WORDS])


# -----------------------------------------------------------------------------
# Tool wrappers — what strategies hand to the LLM provider.
# -----------------------------------------------------------------------------
WIKIPEDIA_SEARCH_TOOL: Tool = Tool(
    name="wikipedia_search",
    description=(
        "Search English Wikipedia for articles relevant to a query and return "
        "the top 5 matching article titles."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Free-text search query.",
            },
        },
        "required": ["query"],
    },
    execute=wikipedia_search,
)


WIKIPEDIA_FETCH_TOOL: Tool = Tool(
    name="wikipedia_fetch",
    description=(
        "Fetch the first 500 words of the plain-text body of a Wikipedia "
        "article by its exact title. Use a title returned by wikipedia_search."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Exact Wikipedia article title.",
            },
        },
        "required": ["title"],
    },
    execute=wikipedia_fetch,
)


WIKIPEDIA_TOOLS: list[Tool] = [WIKIPEDIA_SEARCH_TOOL, WIKIPEDIA_FETCH_TOOL]
