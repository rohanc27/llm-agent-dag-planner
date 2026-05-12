from __future__ import annotations

"""Dev helper — probe live GitHub data so the benchmark's gold answers
match the API's current state. Not part of the eval; run by hand before
authoring `benchmarks/github/tasks.json`.

Run:

    python scripts/_probe_github.py
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


async def _print(title: str, value):
    print(f"\n--- {title} ---")
    if isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(value)


async def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    auth = "(authenticated)" if os.environ.get("GITHUB_TOKEN") else "(unauthenticated — 60 req/hr cap)"
    print(f"GitHub probe {auth}")

    # ===== Star comparisons for "embarrassingly parallel" candidates =====
    star_repos = [
        ("torvalds", "linux"),
        ("rust-lang", "rust"),
        ("golang", "go"),
        ("python", "cpython"),
        ("microsoft", "typescript"),
        ("microsoft", "vscode"),
        ("facebook", "react"),
        ("vuejs", "vue"),
        ("vuejs", "core"),
        ("nodejs", "node"),
        ("denoland", "deno"),
        ("oven-sh", "bun"),
        ("vercel", "next.js"),
        ("remix-run", "remix"),
        ("sveltejs", "kit"),
        ("kubernetes", "kubernetes"),
        ("hashicorp", "terraform"),
        ("django", "django"),
        ("rails", "rails"),
        ("expressjs", "express"),
        ("laravel", "laravel"),
        ("tailwindlabs", "tailwindcss"),
        ("mui", "material-ui"),
        ("chakra-ui", "chakra-ui"),
        ("tensorflow", "tensorflow"),
        ("pytorch", "pytorch"),
        ("keras-team", "keras"),
        ("scikit-learn", "scikit-learn"),
        ("docker", "cli"),
        ("kubernetes", "kubectl"),
        ("redis", "redis"),
        ("elastic", "elasticsearch"),
        ("postgres", "postgres"),
    ]
    print("\n========== get_repo (stars / forks / language / open_issues) ==========")
    repo_data = await asyncio.gather(
        *(github_get_repo(o, r) for o, r in star_repos),
        return_exceptions=True,
    )
    for (o, r), info in zip(star_repos, repo_data):
        if isinstance(info, Exception):
            print(f"  {o}/{r}: EXC {info}")
            continue
        if "error" in info:
            print(f"  {o}/{r}: {info['error']}")
            continue
        print(
            f"  {o}/{r:>18}  stars={info['stars']:>8}  forks={info['forks']:>7}  "
            f"lang={info['language']!r:>14}  open_issues={info['open_issues']}"
        )

    # ===== Open issue counts (PR-excluded) for comparison tasks =====
    issue_pairs = [
        ("facebook", "react"),
        ("vuejs", "core"),
        ("vuejs", "vue"),
        ("kubernetes", "kubernetes"),
        ("hashicorp", "terraform"),
    ]
    print("\n========== open_issues_count (issues only, no PRs) ==========")
    issue_counts = await asyncio.gather(
        *(github_get_open_issues_count(o, r) for o, r in issue_pairs),
        return_exceptions=True,
    )
    for (o, r), c in zip(issue_pairs, issue_counts):
        print(f"  {o}/{r}: {c}")

    # ===== Latest releases =====
    release_repos = [
        ("nodejs", "node"),
        ("denoland", "deno"),
        ("oven-sh", "bun"),
        ("rust-lang", "rust"),
        ("golang", "go"),
        ("microsoft", "typescript"),
        ("kubernetes", "kubernetes"),
        ("hashicorp", "terraform"),
        ("vercel", "next.js"),
    ]
    print("\n========== latest_release ==========")
    rels = await asyncio.gather(
        *(github_get_latest_release(o, r) for o, r in release_repos),
        return_exceptions=True,
    )
    for (o, r), rel in zip(release_repos, rels):
        if isinstance(rel, Exception):
            print(f"  {o}/{r}: EXC {rel}")
            continue
        if "error" in rel:
            print(f"  {o}/{r}: {rel['error']}")
        else:
            print(f"  {o}/{r}: tag={rel['tag_name']!r:>20}  published={rel['published_at']}")

    # ===== Top contributors =====
    contrib_repos = [
        ("torvalds", "linux"),
        ("facebook", "react"),
        ("vercel", "next.js"),
        ("rust-lang", "rust"),
        ("tensorflow", "tensorflow"),
    ]
    print("\n========== top_contributors (top 3 each) ==========")
    contribs = await asyncio.gather(
        *(github_get_top_contributors(o, r, n=3) for o, r in contrib_repos),
        return_exceptions=True,
    )
    for (o, r), c in zip(contrib_repos, contribs):
        if isinstance(c, Exception):
            print(f"  {o}/{r}: EXC {c}")
            continue
        names = ", ".join(f"{x['login']}({x['contributions']})" for x in c)
        print(f"  {o}/{r}: {names}")

    # ===== Search queries =====
    queries = [
        "machine learning",
        "language:rust",
        "web framework",
        "static site generator",
        "rust web framework",
        "monorepo",
        "graphql server",
        "vector database",
        "ci cd",
        "reverse proxy",
    ]
    print("\n========== search_repos (top 5 each) ==========")
    searches = await asyncio.gather(
        *(github_search_repos(q, n=5) for q in queries),
        return_exceptions=True,
    )
    for q, items in zip(queries, searches):
        print(f"\n  query={q!r}")
        if isinstance(items, Exception):
            print(f"    EXC {items}")
            continue
        for it in items:
            print(f"    {it['owner']}/{it['name']:>30}  stars={it['stars']:>8}  lang={it['language']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
