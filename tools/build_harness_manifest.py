from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from agent_sandbox_eval.reports.markdown import summarize_trajectory
from agent_sandbox_eval.trajectories.replay import iter_events
from agent_sandbox_eval.version import TRAJECTORY_SCHEMA_VERSION


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

EXPECTED_AGENTS = {
    "scripted": "scripted",
    "react-local-solution": "react",
    "noop": "noop",
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


def _run_entry(
    label: str,
    trajectory: Path,
    summary: dict[str, object],
) -> dict[str, object]:
    metadata = RUN_LABELS[label]
    failures = summary["failures"]
    if not isinstance(failures, Counter):
        raise ValueError(f"{label} summary has invalid failure counts")
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_control_runs(
    trajectories: dict[str, Path],
    summaries: dict[str, dict[str, object]],
) -> None:
    resolved_paths = {path.resolve() for path in trajectories.values()}
    digests = {_sha256(path) for path in trajectories.values()}
    if len(resolved_paths) != 3 or len(digests) != 3:
        raise ValueError("manifest requires three distinct control trajectories")

    task_ids: dict[str, set[str]] = {}
    for label, path in trajectories.items():
        events = iter_events(path)
        run_ids = {event.get("run_id") for event in events}
        if (
            len(run_ids) != 1
            or None in run_ids
            or any(event.get("schema_version") != TRAJECTORY_SCHEMA_VERSION for event in events)
            or any(event.get("step_index") != index for index, event in enumerate(events))
        ):
            raise ValueError(f"{label} trajectory has invalid event identity or ordering")
        run_starts = [event for event in events if event.get("event_type") == "run_start"]
        run_ends = [event for event in events if event.get("event_type") == "run_end"]
        grades = [event for event in events if event.get("event_type") == "grader_result"]
        starts = [event for event in events if event.get("event_type") == "task_start"]
        if (
            len(run_starts) != 1
            or len(run_ends) != 1
            or events[0].get("event_type") != "run_start"
            or events[-1].get("event_type") != "run_end"
        ):
            raise ValueError(f"{label} trajectory has invalid run boundaries")
        grade_ids = [event.get("task_id") for event in grades]
        start_ids = [event.get("task_id") for event in starts]
        if (
            len(grades) != 25
            or len(starts) != 25
            or any(not isinstance(event.get("passed"), bool) for event in grades)
            or any(not isinstance(task_id, str) or not task_id for task_id in grade_ids)
            or len(set(grade_ids)) != 25
            or set(start_ids) != set(grade_ids)
        ):
            raise ValueError(f"{label} control must contain exactly 25 unique graded tasks")
        run_end = run_ends[0]
        passed = int(summaries[label]["passed"])
        if summaries[label]["agent"] != EXPECTED_AGENTS[label]:
            raise ValueError(f"{label} trajectory records the wrong agent identity")
        if run_end.get("total_tasks") != 25 or run_end.get("passed_tasks") != passed:
            raise ValueError(f"{label} run_end disagrees with grader evidence")
        if int(summaries[label]["model_calls"]) != 0:
            raise ValueError(f"{label} control must contain zero model calls")
        if label == "noop" and int(summaries[label]["tool_calls"]) != 0:
            raise ValueError("noop negative control must contain zero tool calls")
        task_ids[label] = {str(task_id) for task_id in grade_ids}

    if len({frozenset(ids) for ids in task_ids.values()}) != 1:
        raise ValueError("control trajectories must grade the same 25 task ids")
    if int(summaries["scripted"]["passed"]) != 25:
        raise ValueError("scripted oracle must pass exactly 25 of 25 tasks")
    if int(summaries["react-local-solution"]["passed"]) != 25:
        raise ValueError("ReAct local-solution control must pass exactly 25 of 25 tasks")
    if int(summaries["noop"]["passed"]) != 0:
        raise ValueError("noop negative control must pass exactly 0 of 25 tasks")
    for label in ["scripted", "react-local-solution"]:
        grades = summaries[label]["grader_events"]
        if not isinstance(grades, list) or any(event.get("passed") is not True for event in grades):
            raise ValueError(f"{label} control must contain 25 explicit passing grader results")
    noop_failures = summaries["noop"]["failures"]
    if not isinstance(noop_failures, Counter) or noop_failures != Counter({"no_progress": 25}):
        raise ValueError("noop negative control must record no_progress for all 25 tasks")
    noop_grades = summaries["noop"]["grader_events"]
    if not isinstance(noop_grades, list) or any(
        event.get("passed") is not False or event.get("failure_mode") != "no_progress"
        for event in noop_grades
    ):
        raise ValueError("noop negative control must contain explicit no_progress failures")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripted", type=Path, required=True)
    parser.add_argument("--react-local-solution", type=Path, required=True)
    parser.add_argument("--noop", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    trajectories = {
        "scripted": args.scripted,
        "react-local-solution": args.react_local_solution,
        "noop": args.noop,
    }
    summaries = {
        label: summarize_trajectory(path)
        for label, path in trajectories.items()
    }
    _validate_control_runs(trajectories, summaries)

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
            _run_entry("scripted", args.scripted, summaries["scripted"]),
            _run_entry(
                "react-local-solution",
                args.react_local_solution,
                summaries["react-local-solution"],
            ),
            _run_entry("noop", args.noop, summaries["noop"]),
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
