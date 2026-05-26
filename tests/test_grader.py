from pathlib import Path

from agent_sandbox_eval.benchmarks.schema import SuccessCriteria
from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.eval.grader import Grader
from agent_sandbox_eval.sandbox.docker import DockerSandbox
from agent_sandbox_eval.eval.failure_analysis import analyze_failure, classify_failure
from agent_sandbox_eval.tools.base import ToolResult


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
