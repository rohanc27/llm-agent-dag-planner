from __future__ import annotations

"""GitHub API tools for the custom benchmark.

Five async tools wrapping ``https://api.github.com``:

* :func:`github_get_repo`              — stars / forks / language / etc.
* :func:`github_get_latest_release`    — latest release tag / name / date
* :func:`github_get_top_contributors`  — top-N contributors by commit count
* :func:`github_get_open_issues_count` — count of OPEN issues (excludes PRs)
* :func:`github_search_repos`          — repository search, sorted by stars

A ``GITHUB_TOKEN`` env var raises the rate limit from 60 req/hr to 5000
req/hr. Search endpoints have their own narrower limit (10/min unauth,
30/min auth).
"""

import os
from typing import Any, Optional

import httpx

from src.tools.base import Tool

# Best-effort .env loading at import time so the GitHub tools pick up
# ``GITHUB_TOKEN`` from any entry point (eval harness, scripts, ad-hoc
# REPL). Guarded against missing python-dotenv so the import never breaks
# in environments where it isn't installed.
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv()
except ImportError:
    pass

GITHUB_API: str = "https://api.github.com"
USER_AGENT: str = "llm-agent-dag-planner/0.1 (rohanc@gmail.com)"
_DEFAULT_TIMEOUT: float = 20.0


def _headers() -> dict[str, str]:
    """Standard GitHub REST headers + bearer auth if a token is in env."""
    h: dict[str, str] = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
async def github_get_repo(owner: str, repo: str) -> dict[str, Any]:
    """Return a slim repo-metadata dict.

    On 404 returns ``{"error": "repo <owner>/<repo> not found"}`` so
    callers / strategies can surface the failure without an exception.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, headers=_headers()) as client:
        response = await client.get(url)
        if response.status_code == 404:
            return {"error": f"repo {owner}/{repo} not found"}
        response.raise_for_status()
        data = response.json()
    return {
        "stars": int(data.get("stargazers_count", 0) or 0),
        "forks": int(data.get("forks_count", 0) or 0),
        "language": data.get("language"),
        "description": data.get("description"),
        "open_issues": int(data.get("open_issues_count", 0) or 0),
        "created_at": data.get("created_at", "") or "",
        "updated_at": data.get("updated_at", "") or "",
    }


async def github_get_latest_release(owner: str, repo: str) -> dict[str, Any]:
    """Return ``{tag_name, name, published_at}`` for the repo's latest
    release. Repos with no GitHub releases (e.g. ``torvalds/linux``)
    return ``{"error": "No releases"}``.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/latest"
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, headers=_headers()) as client:
        response = await client.get(url)
        if response.status_code == 404:
            return {"error": "No releases"}
        response.raise_for_status()
        data = response.json()
    return {
        "tag_name": data.get("tag_name", "") or "",
        "name": data.get("name"),
        "published_at": data.get("published_at", "") or "",
    }


async def github_get_top_contributors(
    owner: str, repo: str, n: int = 5
) -> list[dict[str, Any]]:
    """Return up to ``n`` top contributors by commit count.

    GitHub orders contributors by ``contributions`` descending by default.
    Anonymous contributors are excluded.

    Edge cases the GitHub API surfaces here, both returned as ``[]``:

    * **204 No Content** — empty repo with no contributors.
    * **403 Forbidden** — repository has too many contributors to enumerate
      via the REST endpoint (e.g. ``torvalds/linux``). This is documented
      behavior, distinct from rate-limit 403s. Returning ``[]`` keeps the
      caller's interface consistent; strategies can detect the empty list
      and recover (e.g. fall back to a search-based heuristic).
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contributors"
    params: dict[str, Any] = {"per_page": max(1, min(n, 100)), "anon": "false"}
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, headers=_headers()) as client:
        response = await client.get(url, params=params)
        if response.status_code in (204, 403):
            return []
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, list):
        return []
    return [
        {
            "login": c.get("login", "") or "",
            "contributions": int(c.get("contributions", 0) or 0),
        }
        for c in data[:n]
    ]


async def github_get_open_issues_count(owner: str, repo: str) -> int:
    """Count of OPEN ISSUES — *excluding* pull requests.

    The plain ``/repos/{owner}/{repo}`` endpoint's ``open_issues_count``
    field includes PRs, which is misleading. We use the search API with
    ``is:issue is:open repo:owner/repo`` to get the issues-only count.
    """
    url = f"{GITHUB_API}/search/issues"
    params: dict[str, Any] = {
        "q": f"is:issue is:open repo:{owner}/{repo}",
        "per_page": 1,
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, headers=_headers()) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    return int(data.get("total_count", 0) or 0)


async def github_search_repos(query: str, n: int = 10) -> list[dict[str, Any]]:
    """Search public repos, sorted by stars (descending). Returns slim
    records of ``{owner, name, stars, language}`` capped at ``n``.
    """
    url = f"{GITHUB_API}/search/repositories"
    params: dict[str, Any] = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": max(1, min(n, 100)),
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, headers=_headers()) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    items = data.get("items", []) or []
    return [
        {
            "owner": (item.get("owner") or {}).get("login", "") or "",
            "name": item.get("name", "") or "",
            "stars": int(item.get("stargazers_count", 0) or 0),
            "language": item.get("language"),
        }
        for item in items[:n]
    ]


# ---------------------------------------------------------------------------
# Tool wrappers — what strategies hand to the LLM provider.
# ---------------------------------------------------------------------------
GITHUB_GET_REPO_TOOL: Tool = Tool(
    name="github_get_repo",
    description=(
        "Fetch metadata for a GitHub repository: stars, forks, primary "
        "language, description, open issue count, and created/updated "
        "timestamps. Returns {'error': ...} if the repo doesn't exist."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "Repository owner or organization (e.g. 'torvalds').",
            },
            "repo": {
                "type": "string",
                "description": "Repository name (e.g. 'linux').",
            },
        },
        "required": ["owner", "repo"],
    },
    execute=github_get_repo,
)


GITHUB_GET_LATEST_RELEASE_TOOL: Tool = Tool(
    name="github_get_latest_release",
    description=(
        "Fetch the latest release of a GitHub repository: tag, optional "
        "release name, and publication timestamp. Returns "
        "{'error': 'No releases'} for repos that haven't tagged a release."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "Repository owner."},
            "repo": {"type": "string", "description": "Repository name."},
        },
        "required": ["owner", "repo"],
    },
    execute=github_get_latest_release,
)


GITHUB_GET_TOP_CONTRIBUTORS_TOOL: Tool = Tool(
    name="github_get_top_contributors",
    description=(
        "Return the top contributors (by commit count) to a GitHub "
        "repository: a list of {login, contributions} pairs capped at n."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "Repository owner."},
            "repo": {"type": "string", "description": "Repository name."},
            "n": {
                "type": "integer",
                "description": "Maximum number of contributors to return (default 5).",
            },
        },
        "required": ["owner", "repo"],
    },
    execute=github_get_top_contributors,
)


GITHUB_GET_OPEN_ISSUES_COUNT_TOOL: Tool = Tool(
    name="github_get_open_issues_count",
    description=(
        "Return the count of OPEN issues (excluding pull requests) for a "
        "GitHub repository. Uses the search API for accuracy — the bare "
        "/repos endpoint's open_issues field conflates issues with PRs."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "Repository owner."},
            "repo": {"type": "string", "description": "Repository name."},
        },
        "required": ["owner", "repo"],
    },
    execute=github_get_open_issues_count,
)


GITHUB_SEARCH_REPOS_TOOL: Tool = Tool(
    name="github_search_repos",
    description=(
        "Search public GitHub repositories by free-text query, sorted by "
        "stars descending. Returns a list of {owner, name, stars, "
        "language} entries (no description field — use github_get_repo if "
        "you need that)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Free-text search query, e.g. 'machine learning', "
                    "'language:rust', or 'topic:web-framework'."
                ),
            },
            "n": {
                "type": "integer",
                "description": "Maximum number of results to return (default 10).",
            },
        },
        "required": ["query"],
    },
    execute=github_search_repos,
)


GITHUB_TOOLS: list[Tool] = [
    GITHUB_GET_REPO_TOOL,
    GITHUB_GET_LATEST_RELEASE_TOOL,
    GITHUB_GET_TOP_CONTRIBUTORS_TOOL,
    GITHUB_GET_OPEN_ISSUES_COUNT_TOOL,
    GITHUB_SEARCH_REPOS_TOOL,
]
