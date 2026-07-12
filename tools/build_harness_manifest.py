from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from agent_sandbox_eval.reports.markdown import summarize_trajectory


RUN_LABELS = {
    "scripted": {
        "classification": "scripted_oracle",
        "claim": "Validates task solutions, Docker execution, grading, recording, reports, and replay.",
        "agent_capability_result": False,
    },
    "react-local-solution": {
        "classification": "deterministic_harness_validation",
        "claim": "Validates the ReAct loop with task-provided solution metadata instead of model reasoning.",
        "agent_capability_result": False,
    },
    "noop": {
        "classification": "negative_control",
        "claim": "Validates failure recording and no-progress classification when the agent takes no action.",
        "agent_capability_result": False,
    },
}


def _docker_version() -> str:
    result = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "unavailable"


def _git_commit() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _run_entry(label: str, trajectory: Path) -> dict[str, object]:
    summary = summarize_trajectory(trajectory)
    metadata = RUN_LABELS[label]
    failures = summary["failures"]
    assert isinstance(failures, Counter)
    return {
        "label": label,
        **metadata,
        "trajectory": str(trajectory),
        "tasks": summary["total"],
        "passed": summary["passed"],
        "passRate": summary["pass_rate"],
        "averageScore": summary["average_score"],
        "toolCalls": summary["tool_calls"],
        "averageToolCalls": summary["avg_tool_calls"],
        "averageRuntimeMs": summary["avg_runtime_ms"],
        "timeoutRate": summary["timeout_rate"],
        "verificationRate": summary["verification_rate"],
        "taskOrGraderBugCount": summary["task_or_grader_bug_count"],
        "modelCalls": summary["model_calls"],
        "inputTokens": summary["input_tokens"],
        "outputTokens": summary["output_tokens"],
        "estimatedCostUsd": summary["estimated_cost_usd"],
        "costCoverage": summary["cost_coverage"],
        "failureModes": dict(failures),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripted", type=Path, required=True)
    parser.add_argument("--react-local-solution", type=Path, required=True)
    parser.add_argument("--noop", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(UTC).isoformat(),
        "taskPackCommit": _git_commit(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "dockerServer": _docker_version(),
            "image": "python:3.13-slim",
        },
        "scope": "Harness validation only. No model or agent capability result is included.",
        "liveModelResults": None,
        "runs": [
            _run_entry("scripted", args.scripted),
            _run_entry("react-local-solution", args.react_local_solution),
            _run_entry("noop", args.noop),
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
