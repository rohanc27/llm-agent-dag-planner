from __future__ import annotations

"""Re-verify every gold answer in `benchmarks/github/tasks.json` against
live GitHub state, and auto-patch any drift that is unambiguously
determinable.

Per-task verifiers below mirror the original task design. For each task
we recompute the live gold and compare against the stored gold.

Status decision:
  * MATCH          — live equals stored
  * DRIFTED        — live differs, and the recomputation is unambiguous
                     (clear margin between rank-1 and rank-2 etc.).
                     The script patches tasks.json in place.
  * MANUAL_REVIEW  — live differs and the recomputation is ambiguous
                     (close margin or unstable search top). NOT patched —
                     prints both candidates instead.

Patching never touches ``question`` or ``answer_type`` — only the
``answer`` field. ``tasks.json.bak`` is created before any write.

Search calls are paced to stay safely under the 30/min /search rate
limit (with a token) by spacing them ≥ ``SEARCH_SLEEP_SEC`` apart.

Idempotency: a second run after the first should produce all MATCH.

Run:

    python scripts/reverify_github_tasks.py
"""

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

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

load_dotenv(REPO_ROOT / ".env")

TASKS_PATH = REPO_ROOT / "benchmarks" / "github" / "tasks.json"
BAK_PATH = REPO_ROOT / "benchmarks" / "github" / "tasks.json.bak"

# Pacing constants — applied to /search/repositories AND /search/issues,
# both of which share the 30/min search-API budget.
SEARCH_SLEEP_SEC: float = 2.0

# Ambiguity thresholds (margin = (rank1 - rank2) / rank1).
STARS_MARGIN: float = 0.02
FORKS_MARGIN: float = 0.02
ISSUES_MARGIN: float = 0.15  # issues fluctuate more than star counts
CONTRIB_MARGIN: float = 0.05

# Caches keyed by query/repo to dedupe across the 25 tasks.
_search_cache: dict[str, list[dict[str, Any]]] = {}
_issues_count_cache: dict[tuple[str, str], int] = {}
_last_search_time: float = 0.0


# ---------------------------------------------------------------------------
# Paced wrappers
# ---------------------------------------------------------------------------
async def _pace_search() -> None:
    """Sleep just long enough to keep at least ``SEARCH_SLEEP_SEC`` between
    consecutive /search/* calls."""
    global _last_search_time
    if _last_search_time > 0:
        gap = time.perf_counter() - _last_search_time
        if gap < SEARCH_SLEEP_SEC:
            await asyncio.sleep(SEARCH_SLEEP_SEC - gap)
    _last_search_time = time.perf_counter()


async def cached_search(query: str, n: int = 5) -> list[dict[str, Any]]:
    """Cache by query; under-the-hood always fetch up to 5 results, then slice."""
    if query in _search_cache:
        return _search_cache[query][:n]
    await _pace_search()
    result = await github_search_repos(query, n=max(n, 5))
    _search_cache[query] = result
    return result[:n]


async def cached_issues_count(owner: str, repo: str) -> int:
    key = (owner, repo)
    if key in _issues_count_cache:
        return _issues_count_cache[key]
    await _pace_search()  # /search/issues shares the search budget
    count = await github_get_open_issues_count(owner, repo)
    _issues_count_cache[key] = count
    return count


def _margin(higher: float, lower: float) -> float:
    if higher <= 0:
        return 0.0
    return (higher - lower) / higher


# ---------------------------------------------------------------------------
# Per-task verifiers
# Each returns: {"value": str, "unambiguous": bool, "details": Any}
# ---------------------------------------------------------------------------
async def v_gh_01() -> dict:
    """Among linux/rust/go/cpython, which has the most stars?"""
    repos = [
        ("torvalds", "linux"),
        ("rust-lang", "rust"),
        ("golang", "go"),
        ("python", "cpython"),
    ]
    infos = await asyncio.gather(*(github_get_repo(o, r) for o, r in repos))
    ranked = sorted(
        [(f"{o}/{r}", infos[i]["stars"]) for i, (o, r) in enumerate(repos)],
        key=lambda x: -x[1],
    )
    return {
        "value": ranked[0][0],
        "unambiguous": _margin(ranked[0][1], ranked[1][1]) > STARS_MARGIN,
        "details": ranked,
    }


async def v_gh_02() -> dict:
    """Languages of vscode/react/go/rust."""
    repos = [
        ("microsoft", "vscode"),
        ("facebook", "react"),
        ("golang", "go"),
        ("rust-lang", "rust"),
    ]
    infos = await asyncio.gather(*(github_get_repo(o, r) for o, r in repos))
    parts = [f"{o}/{r}: {infos[i]['language']}" for i, (o, r) in enumerate(repos)]
    return {"value": ", ".join(parts), "unambiguous": True, "details": parts}


async def v_gh_03() -> dict:
    """Among node/deno/bun, which has the most stars?"""
    repos = [("nodejs", "node"), ("denoland", "deno"), ("oven-sh", "bun")]
    infos = await asyncio.gather(*(github_get_repo(o, r) for o, r in repos))
    ranked = sorted(
        [(f"{o}/{r}", infos[i]["stars"]) for i, (o, r) in enumerate(repos)],
        key=lambda x: -x[1],
    )
    return {
        "value": ranked[0][0],
        "unambiguous": _margin(ranked[0][1], ranked[1][1]) > STARS_MARGIN,
        "details": ranked,
    }


async def v_gh_04() -> dict:
    """Among typescript/go/rust, which has the most stars?"""
    repos = [("microsoft", "typescript"), ("golang", "go"), ("rust-lang", "rust")]
    infos = await asyncio.gather(*(github_get_repo(o, r) for o, r in repos))
    ranked = sorted(
        [(f"{o}/{r}", infos[i]["stars"]) for i, (o, r) in enumerate(repos)],
        key=lambda x: -x[1],
    )
    return {
        "value": ranked[0][0],
        "unambiguous": _margin(ranked[0][1], ranked[1][1]) > STARS_MARGIN,
        "details": ranked,
    }


async def v_gh_05() -> dict:
    """Among kubernetes/terraform/docker.cli, which has the most forks?"""
    repos = [
        ("kubernetes", "kubernetes"),
        ("hashicorp", "terraform"),
        ("docker", "cli"),
    ]
    infos = await asyncio.gather(*(github_get_repo(o, r) for o, r in repos))
    ranked = sorted(
        [(f"{o}/{r}", infos[i]["forks"]) for i, (o, r) in enumerate(repos)],
        key=lambda x: -x[1],
    )
    return {
        "value": ranked[0][0],
        "unambiguous": _margin(ranked[0][1], ranked[1][1]) > FORKS_MARGIN,
        "details": ranked,
    }


async def v_gh_06() -> dict:
    """Languages of django/rails/express/laravel."""
    repos = [
        ("django", "django"),
        ("rails", "rails"),
        ("expressjs", "express"),
        ("laravel", "laravel"),
    ]
    infos = await asyncio.gather(*(github_get_repo(o, r) for o, r in repos))
    parts = [f"{o}/{r}: {infos[i]['language']}" for i, (o, r) in enumerate(repos)]
    return {"value": ", ".join(parts), "unambiguous": True, "details": parts}


async def v_gh_07() -> dict:
    """Among next.js/remix/kit, which has the most stars?"""
    repos = [("vercel", "next.js"), ("remix-run", "remix"), ("sveltejs", "kit")]
    infos = await asyncio.gather(*(github_get_repo(o, r) for o, r in repos))
    ranked = sorted(
        [(f"{o}/{r}", infos[i]["stars"]) for i, (o, r) in enumerate(repos)],
        key=lambda x: -x[1],
    )
    return {
        "value": ranked[0][0],
        "unambiguous": _margin(ranked[0][1], ranked[1][1]) > STARS_MARGIN,
        "details": ranked,
    }


async def v_gh_08() -> dict:
    """Open issues (issues only) react vs vue/core — more?"""
    pairs = [("facebook", "react"), ("vuejs", "core")]
    counts = await asyncio.gather(*(cached_issues_count(o, r) for o, r in pairs))
    ranked = sorted(zip([f"{o}/{r}" for o, r in pairs], counts), key=lambda x: -x[1])
    return {
        "value": ranked[0][0],
        "unambiguous": _margin(ranked[0][1], ranked[1][1]) > ISSUES_MARGIN,
        "details": ranked,
    }


async def v_gh_09() -> dict:
    """Among tailwind/material-ui/chakra-ui, which has the FEWEST stars?"""
    repos = [
        ("tailwindlabs", "tailwindcss"),
        ("mui", "material-ui"),
        ("chakra-ui", "chakra-ui"),
    ]
    infos = await asyncio.gather(*(github_get_repo(o, r) for o, r in repos))
    ranked_asc = sorted(
        [(f"{o}/{r}", infos[i]["stars"]) for i, (o, r) in enumerate(repos)],
        key=lambda x: x[1],
    )
    return {
        "value": ranked_asc[0][0],
        "unambiguous": _margin(ranked_asc[1][1], ranked_asc[0][1]) > STARS_MARGIN,
        "details": ranked_asc,
    }


async def v_gh_10() -> dict:
    """Languages of tensorflow/pytorch/keras."""
    repos = [("tensorflow", "tensorflow"), ("pytorch", "pytorch"), ("keras-team", "keras")]
    infos = await asyncio.gather(*(github_get_repo(o, r) for o, r in repos))
    parts = [f"{o}/{r}: {infos[i]['language']}" for i, (o, r) in enumerate(repos)]
    return {"value": ", ".join(parts), "unambiguous": True, "details": parts}


async def v_gh_11() -> dict:
    """Search 'rust web framework' — top 3 latest release tags."""
    top3 = await cached_search("rust web framework", n=3)
    rels = await asyncio.gather(
        *(github_get_latest_release(r["owner"], r["name"]) for r in top3)
    )
    parts = []
    for repo, rel in zip(top3, rels):
        tag = rel.get("tag_name") or rel.get("error") or "<unknown>"
        parts.append(f"{repo['owner']}/{repo['name']}: {tag}")
    return {"value": ", ".join(parts), "unambiguous": True, "details": parts}


async def v_gh_12() -> dict:
    """Search 'static site generator' — top 3 latest release tags."""
    top3 = await cached_search("static site generator", n=3)
    rels = await asyncio.gather(
        *(github_get_latest_release(r["owner"], r["name"]) for r in top3)
    )
    parts = []
    for repo, rel in zip(top3, rels):
        tag = rel.get("tag_name") or rel.get("error") or "<unknown>"
        parts.append(f"{repo['owner']}/{repo['name']}: {tag}")
    return {"value": ", ".join(parts), "unambiguous": True, "details": parts}


async def v_gh_13() -> dict:
    """Search 'monorepo' — top 3, which has most open issues?"""
    top3 = await cached_search("monorepo", n=3)
    counts = await asyncio.gather(
        *(cached_issues_count(r["owner"], r["name"]) for r in top3)
    )
    ranked = sorted(
        zip([f"{r['owner']}/{r['name']}" for r in top3], counts),
        key=lambda x: -x[1],
    )
    return {
        "value": ranked[0][0],
        "unambiguous": _margin(ranked[0][1], ranked[1][1]) > ISSUES_MARGIN,
        "details": ranked,
    }


async def v_gh_14() -> dict:
    """Search 'graphql server' — top 3, which has most forks?"""
    top3 = await cached_search("graphql server", n=3)
    infos = await asyncio.gather(
        *(github_get_repo(r["owner"], r["name"]) for r in top3)
    )
    ranked = sorted(
        [
            (f"{r['owner']}/{r['name']}", infos[i]["forks"])
            for i, r in enumerate(top3)
        ],
        key=lambda x: -x[1],
    )
    return {
        "value": ranked[0][0],
        "unambiguous": _margin(ranked[0][1], ranked[1][1]) > FORKS_MARGIN,
        "details": ranked,
    }


async def v_gh_15() -> dict:
    """Search 'vector database' — top 3, top contributor login of each."""
    top3 = await cached_search("vector database", n=3)
    contribs = await asyncio.gather(
        *(github_get_top_contributors(r["owner"], r["name"], n=1) for r in top3)
    )
    parts = []
    for repo, lst in zip(top3, contribs):
        login = lst[0]["login"] if lst else "<none>"
        parts.append(f"{repo['owner']}/{repo['name']}: {login}")
    return {"value": ", ".join(parts), "unambiguous": True, "details": parts}


async def v_gh_16() -> dict:
    """Search 'reverse proxy' — top 3, which has most open issues?"""
    top3 = await cached_search("reverse proxy", n=3)
    counts = await asyncio.gather(
        *(cached_issues_count(r["owner"], r["name"]) for r in top3)
    )
    ranked = sorted(
        zip([f"{r['owner']}/{r['name']}" for r in top3], counts),
        key=lambda x: -x[1],
    )
    return {
        "value": ranked[0][0],
        "unambiguous": _margin(ranked[0][1], ranked[1][1]) > ISSUES_MARGIN,
        "details": ranked,
    }


async def v_gh_17() -> dict:
    """Search 'machine learning' — top 3, which has most open issues?"""
    top3 = await cached_search("machine learning", n=3)
    counts = await asyncio.gather(
        *(cached_issues_count(r["owner"], r["name"]) for r in top3)
    )
    ranked = sorted(
        zip([f"{r['owner']}/{r['name']}" for r in top3], counts),
        key=lambda x: -x[1],
    )
    return {
        "value": ranked[0][0],
        "unambiguous": _margin(ranked[0][1], ranked[1][1]) > ISSUES_MARGIN,
        "details": ranked,
    }


async def v_gh_18() -> dict:
    """Search 'web framework' — top 3, list primary languages."""
    top3 = await cached_search("web framework", n=3)
    parts = [f"{r['owner']}/{r['name']}: {r['language']}" for r in top3]
    return {"value": ", ".join(parts), "unambiguous": True, "details": parts}


async def v_gh_19() -> dict:
    """Search 'language:rust' — top 3 owners (comma-separated)."""
    top3 = await cached_search("language:rust", n=3)
    return {
        "value": ", ".join(r["owner"] for r in top3),
        "unambiguous": True,
        "details": top3,
    }


async def v_gh_20() -> dict:
    """Search 'language:rust' — which of top 3 has >150k stars?"""
    top3 = await cached_search("language:rust", n=3)
    above = [r for r in top3 if r["stars"] > 150_000]
    if len(above) == 1:
        r = above[0]
        return {
            "value": f"{r['owner']}/{r['name']}",
            "unambiguous": True,
            "details": top3,
        }
    if len(above) == 0:
        return {
            "value": "<none of the top 3 has >150k stars>",
            "unambiguous": False,
            "details": top3,
        }
    names = [f"{r['owner']}/{r['name']}" for r in above]
    return {
        "value": " or ".join(names),
        "unambiguous": False,
        "details": top3,
    }


async def v_gh_21() -> dict:
    """Search 'machine learning' — top result's language."""
    top = await cached_search("machine learning", n=3)
    if not top:
        return {"value": "<empty>", "unambiguous": False, "details": []}
    # Stable when top stars >> #2 stars
    unambig = _margin(top[0]["stars"], top[1]["stars"]) > STARS_MARGIN if len(top) > 1 else True
    return {
        "value": top[0]["language"] or "<null>",
        "unambiguous": unambig,
        "details": top[:2],
    }


async def v_gh_22() -> dict:
    """Search 'static site generator' — top result's latest release tag."""
    top = await cached_search("static site generator", n=3)
    if not top:
        return {"value": "<empty>", "unambiguous": False, "details": []}
    unambig = _margin(top[0]["stars"], top[1]["stars"]) > STARS_MARGIN if len(top) > 1 else True
    rel = await github_get_latest_release(top[0]["owner"], top[0]["name"])
    tag = rel.get("tag_name") or rel.get("error") or "<unknown>"
    return {"value": tag, "unambiguous": unambig, "details": (top[:2], rel)}


async def v_gh_23() -> dict:
    """Search 'vector database' — top result's top contributor login."""
    top = await cached_search("vector database", n=3)
    if not top:
        return {"value": "<empty>", "unambiguous": False, "details": []}
    unambig = _margin(top[0]["stars"], top[1]["stars"]) > STARS_MARGIN if len(top) > 1 else True
    contribs = await github_get_top_contributors(top[0]["owner"], top[0]["name"], n=2)
    if not contribs:
        return {"value": "<no contributors>", "unambiguous": False, "details": top[:2]}
    if len(contribs) > 1:
        contrib_margin = _margin(contribs[0]["contributions"], contribs[1]["contributions"])
        if contrib_margin <= CONTRIB_MARGIN:
            unambig = False
    return {"value": contribs[0]["login"], "unambiguous": unambig, "details": (top[:2], contribs)}


async def v_gh_24() -> dict:
    """Search 'monorepo' — top result's open issue count."""
    top = await cached_search("monorepo", n=3)
    if not top:
        return {"value": "<empty>", "unambiguous": False, "details": []}
    unambig = _margin(top[0]["stars"], top[1]["stars"]) > STARS_MARGIN if len(top) > 1 else True
    count = await cached_issues_count(top[0]["owner"], top[0]["name"])
    return {"value": str(count), "unambiguous": unambig, "details": (top[:2], count)}


async def v_gh_25() -> dict:
    """Search 'reverse proxy' — top result's language."""
    top = await cached_search("reverse proxy", n=3)
    if not top:
        return {"value": "<empty>", "unambiguous": False, "details": []}
    unambig = _margin(top[0]["stars"], top[1]["stars"]) > STARS_MARGIN if len(top) > 1 else True
    return {
        "value": top[0]["language"] or "<null>",
        "unambiguous": unambig,
        "details": top[:2],
    }


VERIFIERS: dict[str, Callable[[], Awaitable[dict]]] = {
    "gh_01": v_gh_01, "gh_02": v_gh_02, "gh_03": v_gh_03, "gh_04": v_gh_04,
    "gh_05": v_gh_05, "gh_06": v_gh_06, "gh_07": v_gh_07, "gh_08": v_gh_08,
    "gh_09": v_gh_09, "gh_10": v_gh_10, "gh_11": v_gh_11, "gh_12": v_gh_12,
    "gh_13": v_gh_13, "gh_14": v_gh_14, "gh_15": v_gh_15, "gh_16": v_gh_16,
    "gh_17": v_gh_17, "gh_18": v_gh_18, "gh_19": v_gh_19, "gh_20": v_gh_20,
    "gh_21": v_gh_21, "gh_22": v_gh_22, "gh_23": v_gh_23, "gh_24": v_gh_24,
    "gh_25": v_gh_25,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
async def main() -> int:
    with open(TASKS_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    matched = 0
    auto_patched = 0
    manual_review: list[dict] = []
    patched_anything = False

    print(f"Re-verifying {len(tasks)} GitHub tasks against live API…")
    print()

    for task in tasks:
        tid = task["id"]
        verifier = VERIFIERS.get(tid)
        if verifier is None:
            print(f"{tid}: <no verifier wired> — skipping")
            continue

        try:
            result = await verifier()
        except Exception as exc:  # noqa: BLE001
            print(f"{tid}: VERIFIER_ERROR — {type(exc).__name__}: {exc}")
            continue

        stored = task["answer"]
        live = result["value"]
        ambiguous = not result["unambiguous"]
        q_short = task["question"][:80]

        if stored == live:
            status = "MATCH"
            matched += 1
        elif ambiguous:
            status = "MANUAL_REVIEW"
            manual_review.append(
                {"id": tid, "stored": stored, "live": live, "details": result["details"]}
            )
        else:
            status = "DRIFTED"
            task["answer"] = live
            auto_patched += 1
            patched_anything = True

        print(f"{tid}: {q_short}{'…' if len(task['question']) > 80 else ''}")
        print(f"  Stored gold:  {stored!r}")
        print(f"  Live gold:    {live!r}")
        print(f"  Status:       {status}")
        if status == "MANUAL_REVIEW":
            print(f"  Details:      {result['details']}")
        print()

    # ---- Write-back -------------------------------------------------------
    if patched_anything:
        shutil.copy(TASKS_PATH, BAK_PATH)
        with open(TASKS_PATH, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Patched tasks.json (backup at {BAK_PATH.name}).")
        print()

    # ---- Summary ----------------------------------------------------------
    print("=" * 60)
    print(f"Total tasks:    {len(tasks)}")
    print(f"Matched:        {matched}")
    print(f"Auto-patched:   {auto_patched}")
    print(f"Manual review:  {len(manual_review)}")
    if manual_review:
        print()
        print("Manual review needed for:")
        for mr in manual_review:
            print(f"  - {mr['id']}: stored={mr['stored']!r}  live={mr['live']!r}")
            print(f"      details: {mr['details']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
