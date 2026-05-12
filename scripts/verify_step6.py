from __future__ import annotations

"""Verify Step 6 — smoke-test the full eval pipeline on 3 tasks.

Equivalent to:

    python -m src.run_eval --strategy react --benchmark hotpotqa --n 3

We shell out so the CLI surface (argparse, exit codes, the
``python -m`` entrypoint) gets exercised end-to-end. The whole run is
~1 minute and well under $0.01.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "src.run_eval",
        "--strategy", "react",
        "--benchmark", "hotpotqa",
        "--n", "3",
    ]
    print(f"$ {' '.join(cmd)}\n", flush=True)
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
