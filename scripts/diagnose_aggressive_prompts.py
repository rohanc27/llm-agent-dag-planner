from __future__ import annotations

"""Offline demonstration of the diversified replan prompt (Ablations 4 + 5
in :mod:`src.strategies.dag_planner_replan`).

No API calls — uses the pure ``_replan_user_message_diversified`` helper
with synthetic history modelled on the actual Phase A traces. Three
scenarios cover the failure modes the diversification machinery is
meant to catch.

Run:

    python scripts/diagnose_aggressive_prompts.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.core.dag import DAG, Task  # noqa: E402
from src.strategies.dag_planner_replan import (  # noqa: E402
    _replan_user_message_diversified,
)


def _print_scenario(label: str, question: str, history) -> None:
    print("=" * 78)
    print(f"SCENARIO: {label}")
    print("=" * 78)
    print(f"Question: {question}")
    print()
    print("Diversified replan prompt the planner sees on attempt #2:")
    print("─" * 78)
    print(_replan_user_message_diversified(question, history))
    print("─" * 78)
    print()


def main() -> int:
    # Scenario 1 — Big Fish: top-1 search returned wrong person; replan
    # should pivot to a different search.
    big_fish_dag = DAG(
        tasks=[
            Task(
                id=0,
                tool="wikipedia_search",
                args={"query": "Big Fish musical composer lyricist"},
                depends_on=[],
            ),
            Task(id=1, tool="wikipedia_fetch", args={"title": "$task_0.0"}, depends_on=[0]),
            Task(
                id=2,
                tool="wikipedia_search",
                args={"query": "Andrew Lippa residential artist theater"},
                depends_on=[1],
            ),
            Task(id=3, tool="wikipedia_fetch", args={"title": "$task_2.0"}, depends_on=[2]),
        ]
    )
    big_fish_outputs = {
        0: ["Robert Lopez", "Alan Menken", "Danny Elfman", "List of musicals by composer: A to L", "Mort Garson"],
        1: "Robert Lopez (born February 23, 1975) is an American songwriter and librettist, best known for co-creating The Book of Mormon and Avenue Q, and for co-writing the songs featured in the Disney animated films Frozen…",
        2: ["The Addams Family (1964 TV series)", "Buffalo, New York", "Chronicon Pictum", "August Wilson Theatre"],
        3: "The Addams Family is an American Gothic sitcom based on Charles Addams's New Yorker cartoons. With an ensemble cast, the 30-minute television series took the unnamed characters in the single-panel gag cartoons…",
    }
    _print_scenario(
        "Big Fish (wrong-article retrieval — top-1 was Robert Lopez, not Andrew Lippa)",
        "At what theater is the composer and lyricist for the musical Big Fish a residential artist?",
        [(big_fish_dag, big_fish_outputs)],
    )

    # Scenario 2 — Bridge bridge with placeholder-shaped malformation in
    # the initial plan: a task got `<not executed>` for one branch.
    chinese_musician_dag = DAG(
        tasks=[
            Task(
                id=0,
                tool="wikipedia_search",
                args={"query": "I Remember AlunaGeorge album"},
                depends_on=[],
            ),
            Task(id=1, tool="wikipedia_fetch", args={"title": "$task_0.0"}, depends_on=[0]),
        ]
    )
    chinese_musician_outputs = {
        0: ["I Remember (AlunaGeorge song)", "Body Music (AlunaGeorge album)"],
        1: "'I Remember' is a song by English electronic music duo AlunaGeorge. The song features American electronic music producer Flume. It was released as a single on 27 April 2016 from their second studio album, I Remember…",
    }
    _print_scenario(
        "Chinese-American musician (search returned a SONG article, not the ALBUM the question references)",
        "When was the Chinese American electronic musician and singer who collaborated on the album I Remember born?",
        [(chinese_musician_dag, chinese_musician_outputs)],
    )

    # Scenario 3 — Multiple attempts: history exceeds 3000-char budget;
    # earlier attempts get dropped.
    long_dag_1 = DAG(
        tasks=[
            Task(id=0, tool="wikipedia_search", args={"query": "Volvo S70"}, depends_on=[]),
            Task(id=1, tool="wikipedia_fetch", args={"title": "$task_0.0"}, depends_on=[0]),
        ]
    )
    long_outputs_1 = {
        0: ["Volvo S70", "Volvo V70", "Volvo Modular Engine", "Volvo 850", "Volvo R"],
        1: "The Volvo S70 is a compact executive car produced by Volvo Cars from 1996 to 2000. The S70 was essentially a facelifted 850 saloon. The S70 was replaced with the Volvo S60. " * 5,
    }
    long_dag_2 = DAG(
        tasks=[
            Task(
                id=0,
                tool="wikipedia_search",
                args={"query": "Volvo S70 all wheel drive history"},
                depends_on=[],
            ),
            Task(id=1, tool="wikipedia_fetch", args={"title": "$task_0.0"}, depends_on=[0]),
        ]
    )
    long_outputs_2 = {
        0: ["Volvo S70", "Volvo all-wheel-drive", "AWD vehicle list"],
        1: "Volvo's all-wheel-drive systems began appearing in the late 1990s. The Volvo XC70 (later renamed Cross Country) introduced Haldex-based AWD… "
        * 5,
    }
    _print_scenario(
        "Two-attempt history (Volvo S70 — both prior searches returned non-empty but unhelpful content; budget pruning may apply)",
        "What was the Volvo S70 essentially modeled after and was the first all wheel drive Volvo?",
        [(long_dag_1, long_outputs_1), (long_dag_2, long_outputs_2)],
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
