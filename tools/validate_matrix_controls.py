from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_sandbox_eval.experiments.control_validation import validate_local_control_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-task-count", type=int, required=True)
    parser.add_argument("--expected-trials", type=int, required=True)
    args = parser.parse_args()

    data = json.loads(args.summary.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("matrix summary must contain an object")
    validate_local_control_summary(
        data,
        expected_task_count=args.expected_task_count,
        expected_trials=args.expected_trials,
    )
    print(f"validated {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
