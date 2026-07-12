from pathlib import Path
import subprocess

import pytest

from agent_sandbox_eval.benchmarks.schema import SuccessCriteria
from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.eval.grader import Grader
from agent_sandbox_eval.sandbox.docker import DockerSandbox
from agent_sandbox_eval.eval.failure_analysis import analyze_failure, classify_failure
from agent_sandbox_eval.tools.base import ToolResult


def _skip_without_docker() -> None:
    docker = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
    if docker.returncode != 0:
        pytest.skip("Docker daemon is not available")


def test_failure_analysis_no_progress() -> None:
    raw = ToolResult(exit_code=1)
    analysis = analyze_failure([], raw)
    assert analysis.failure_mode == "no_progress"
    assert "Agent made no tool calls" in "\n".join(analysis.evidence)
    assert classify_failure([], raw) == "no_progress"


def test_failure_analysis_command_hallucination() -> None:
    raw = ToolResult(exit_code=1)
    tool_results = [ToolResult(stderr="sh: madeupcmd: not found", exit_code=127)]

    analysis = analyze_failure(tool_results, raw)

    assert analysis.failure_mode == "command_hallucination"
    assert any("missing command" in item for item in analysis.evidence)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("planning error: skipped the required dependency", "planning_error"),
        ("wrong tool selected for this state update", "tool_selection_error"),
        ("unrecognized arguments: --destnation", "argument_error"),
        ("environment assumption: expected jq to exist", "environment_assumption"),
        ("state corruption: invalid JSON after write", "state_corruption"),
        ("grader mismatch: expected file differs from task", "grader_or_task_bug"),
        ("unsafe action blocked by sandbox policy", "unsafe_action"),
    ],
)
def test_failure_analysis_expanded_taxonomy(message: str, expected: str) -> None:
    raw = ToolResult(stderr="grader failed", exit_code=1)
    tool_results = [ToolResult(stderr=message, exit_code=1)]
    analysis = analyze_failure(tool_results, raw)
    assert analysis.failure_mode == expected


def test_failure_analysis_distinguishes_timeout_from_step_budget() -> None:
    timeout = analyze_failure([ToolResult(exit_code=124)], ToolResult(exit_code=1))
    budget = analyze_failure(
        [ToolResult(exit_code=0), ToolResult(exit_code=0)],
        ToolResult(exit_code=1),
        max_tool_calls=2,
    )

    assert timeout.failure_mode == "timeout"
    assert budget.failure_mode == "exceeded_budget"


def test_failure_analysis_regression_after_verification() -> None:
    raw = ToolResult(exit_code=1)
    tool_results = [ToolResult(stdout="1 passed", exit_code=0)]

    analysis = analyze_failure(tool_results, raw)

    assert analysis.failure_mode == "regression"


def test_task_success_criteria_loaded() -> None:
    task = load_task(Path("benchmarks/terminal/fix-config-001/task.yaml"))
    assert task.success.type == "command"
    assert "mode=prod" in (task.success.command or "")


def test_file_contains_grader_check() -> None:
    _skip_without_docker()
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    task = task.__class__(
        **{
            **task.__dict__,
            "success": SuccessCriteria(type="file_contains", path="answer.txt", contains="ready"),
        }
    )
    with DockerSandbox(task) as sandbox:
        sandbox.run("printf 'ready\n' > answer.txt")
        result = Grader().grade(task, sandbox, [])

    assert result.passed


def test_json_fields_grader_check() -> None:
    _skip_without_docker()
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    task = task.__class__(
        **{
            **task.__dict__,
            "success": SuccessCriteria(
                type="json_fields",
                path="result.json",
                json_fields={"status": "done", "items.0.name": "alpha"},
            ),
        }
    )
    with DockerSandbox(task) as sandbox:
        sandbox.run("printf '%s\n' '{\"status\":\"done\",\"items\":[{\"name\":\"alpha\"}]}' > result.json")
        result = Grader().grade(task, sandbox, [])

    assert result.passed


def test_json_fields_grader_reports_mismatch() -> None:
    _skip_without_docker()
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    task = task.__class__(
        **{
            **task.__dict__,
            "success": SuccessCriteria(type="json_fields", path="result.json", json_fields={"status": "done"}),
        }
    )
    with DockerSandbox(task) as sandbox:
        sandbox.run("printf '%s\n' '{\"status\":\"pending\"}' > result.json")
        result = Grader().grade(task, sandbox, [])

    assert not result.passed
    assert result.failure_mode
    assert any("status" in item for item in result.evidence)
