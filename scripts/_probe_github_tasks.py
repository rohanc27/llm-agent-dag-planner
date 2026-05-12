from __future__ import annotations

"""Round-2 probe: gather the specific data points needed to commit gold
answers for the 25 GitHub-benchmark tasks. Throwaway helper — not part
of the eval.

Run:

    python scripts/_probe_github_tasks.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.tools.github import (  # noqa: E402
    github_get_latest_release,
    github_get_open_issues_count,
    github_get_repo,
    github_get_top_contributors,
    github_search_repos,
)


async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    print(f"GITHUB_TOKEN set: {bool(os.environ.get('GITHUB_TOKEN'))}")

    # Mixed tasks — for each query, find top 3 then probe the per-repo
    # property the task asks about.
    work = [
        ("rust web framework", "latest_release"),
        ("static site generator", "latest_release"),
        ("monorepo", "open_issues"),
        ("graphql server", "forks"),
        ("vector database", "top_contributors"),
        ("reverse proxy", "open_issues"),
        ("machine learning", "open_issues"),
        ("ci cd", "latest_release"),
        ("language:rust", "forks"),
        ("web framework", "latest_release"),
    ]

    print("\n========== Mixed task data ==========")
    for query, prop in work:
        print(f"\n--- query={query!r}  follow-up={prop} ---")
        top = await github_search_repos(query, n=3)
        for it in top:
            print(f"  {it['owner']}/{it['name']}  stars={it['stars']}  lang={it['language']}")
            if prop == "latest_release":
                rel = await github_get_latest_release(it["owner"], it["name"])
                print(f"    latest_release: {rel}")
            elif prop == "open_issues":
                cnt = await github_get_open_issues_count(it["owner"], it["name"])
                print(f"    open_issues (issues only): {cnt}")
            elif prop == "forks":
                info = await github_get_repo(it["owner"], it["name"])
                print(f"    forks: {info.get('forks')}")
            elif prop == "top_contributors":
                contribs = await github_get_top_contributors(it["owner"], it["name"], n=1)
                top_login = contribs[0]["login"] if contribs else "<empty>"
                print(f"    top contributor: {top_login}  (full: {contribs})")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
