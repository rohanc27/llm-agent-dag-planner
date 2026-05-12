from __future__ import annotations

"""Download HotpotQA dev (distractor) set, filter to bridge tasks, sample 30.

Idempotent CLI — re-runs deterministic sampling but skips the large raw
download if it's already on disk. See SPEC.md § 3 Step 4.

Run with:

    python -m benchmarks.hotpotqa.load
    python -m benchmarks.hotpotqa.load --n 30 --seed 42
    python -m benchmarks.hotpotqa.load --force-download
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import httpx

# Canonical CMU mirror — the URL the HotpotQA project page has linked to
# since the paper's release. Plain HTTP; ``follow_redirects=True`` handles
# any future migration to HTTPS / S3 transparently.
HOTPOT_URL: str = (
    "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json"
)

# Layout. The raw file lives under ``raw/`` (gitignored); the sampled
# tasks.json is committed for reproducibility.
HERE: Path = Path(__file__).resolve().parent
RAW_DIR: Path = HERE / "raw"
RAW_PATH: Path = RAW_DIR / "hotpot_dev_distractor_v1.json"
TASKS_PATH: Path = HERE / "tasks.json"

DEFAULT_N: int = 30
DEFAULT_SEED: int = 42


def download_raw(
    url: str = HOTPOT_URL,
    target: Path = RAW_PATH,
    force: bool = False,
) -> Path:
    """Download the raw HotpotQA dev (distractor) JSON. Idempotent.

    Writes via a ``.tmp`` sibling and renames atomically so a failed
    download never leaves a partial file that future runs would re-use.
    """
    if target.exists() and not force:
        size_mb = target.stat().st_size / (1024 * 1024)
        print(
            f"Raw dev set already present at {target} "
            f"({size_mb:.1f} MB) — skipping download."
        )
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    print(f"Downloading {url}\n         → {target}")

    try:
        with httpx.stream(
            "GET", url, timeout=httpx.Timeout(60.0, connect=20.0), follow_redirects=True
        ) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0)) or None
            downloaded = 0
            with open(tmp, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1 << 20):  # 1 MiB
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(
                            f"  {downloaded / 1e6:6.1f} / {total / 1e6:.1f} MB "
                            f"({pct:5.1f}%)",
                            end="\r",
                            flush=True,
                        )
            if total:
                print()  # finalize progress line
        tmp.replace(target)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise
    return target


def filter_and_sample(
    raw_path: Path,
    n: int = DEFAULT_N,
    seed: int = DEFAULT_SEED,
) -> list[dict[str, Any]]:
    """Load raw JSON, keep ``type == "bridge"``, sample ``n`` with ``seed``.

    Output records use the schema documented in SPEC.md § 3 Step 4.
    """
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(
            f"Expected a JSON array in {raw_path}, got {type(data).__name__}."
        )

    bridge = [ex for ex in data if ex.get("type") == "bridge"]
    if len(bridge) < n:
        raise ValueError(
            f"Only {len(bridge)} bridge examples available in {raw_path}; "
            f"cannot sample {n}."
        )

    rng = random.Random(seed)
    sample = rng.sample(bridge, n)

    return [
        {
            "id": ex["_id"],
            "question": ex["question"],
            "answer": ex["answer"],
            "supporting_facts": ex.get("supporting_facts", []),
            "type": ex["type"],
            "level": ex.get("level", "medium"),
        }
        for ex in sample
    ]


def save_tasks(tasks: list[dict[str, Any]], path: Path = TASKS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


def _display_path(p: Path) -> str:
    """Best-effort short path for the summary line."""
    try:
        return str(p.relative_to(Path.cwd()))
    except ValueError:
        return str(p)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sample HotpotQA bridge tasks.")
    parser.add_argument("--n", type=int, default=DEFAULT_N, help="How many tasks to sample.")
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help="Random seed for sampling."
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download the raw dev set even if it's already on disk.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=HOTPOT_URL,
        help="Source URL for the HotpotQA dev distractor JSON.",
    )
    args = parser.parse_args(argv)

    raw = download_raw(url=args.url, force=args.force_download)
    tasks = filter_and_sample(raw, n=args.n, seed=args.seed)
    save_tasks(tasks, TASKS_PATH)

    print(
        f"\nSampled {len(tasks)} bridge tasks from HotpotQA dev set "
        f"(saved to {_display_path(TASKS_PATH)})"
    )
    print("\nFirst 2 tasks (sanity check):")
    print(json.dumps(tasks[:2], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
