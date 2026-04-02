from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.baseline import run_baseline


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the email triage baseline across tasks.")
    parser.add_argument("--provider", choices=("heuristic", "openai"), default="heuristic")
    parser.add_argument("--tasks", nargs="*", default=["easy", "medium", "hard"])
    args = parser.parse_args()

    results = run_baseline(tasks=args.tasks, provider=args.provider)
    scores = [payload["score"] for payload in results.values()]

    summary = {
        "provider": args.provider,
        "tasks": args.tasks,
        "average_score": round(mean(scores), 4) if scores else 0.0,
        "results": results,
    }

    with open("evaluation_summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
