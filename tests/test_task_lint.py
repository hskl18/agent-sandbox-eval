from dataclasses import replace
from pathlib import Path

from agent_sandbox_eval.benchmarks.lint import lint_task
from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.benchmarks.schema import SuccessCriteria


def test_lint_rejects_weak_grader_without_negative_assertion() -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    task = replace(
        task,
        success=SuccessCriteria(type="file_exists", path="answer.txt"),
    )

    codes = {issue.code for issue in lint_task(task)}

    assert codes >= {"weak-grader", "missing-negative-assertion"}


def test_lint_rejects_mutable_expected_output() -> None:
    task = load_task(Path("benchmarks/terminal/reverse-lines-001/task.yaml"))
    task = replace(
        task,
        success=SuccessCriteria(type="command", command="cmp -s reversed.txt expected.txt"),
    )

    codes = {issue.code for issue in lint_task(task)}

    assert "mutable-expected-output" in codes


def test_lint_rejects_solution_tool_bypass() -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    task = replace(task, allowed_tools=["mcp_state"])

    codes = {issue.code for issue in lint_task(task)}

    assert "solution-tool-bypass" in codes


def test_bundled_tasks_have_no_static_lint_issues() -> None:
    paths = sorted(Path("benchmarks").glob("*/*/task.yaml"))

    issues = [(path, lint_task(load_task(path))) for path in paths]

    assert [(path, task_issues) for path, task_issues in issues if task_issues] == []
