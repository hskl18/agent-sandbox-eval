from __future__ import annotations

import re
from dataclasses import dataclass

from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.eval.grader import Grader
from agent_sandbox_eval.sandbox.docker import DockerSandbox
from agent_sandbox_eval.tools.shell import ShellTool


@dataclass(frozen=True)
class TaskLintIssue:
    code: str
    message: str
    severity: str = "error"


def lint_task(task: Task) -> list[TaskLintIssue]:
    issues: list[TaskLintIssue] = []
    success = task.success

    weak = _weak_grader_reason(task)
    if weak:
        issues.append(TaskLintIssue("weak-grader", weak))
        if not success.negative_assertions:
            issues.append(
                TaskLintIssue(
                    "missing-negative-assertion",
                    "Weak success criteria need success.negative_assertions that reject plausible incorrect output.",
                )
            )

    if success.command and _references_mutable_expected_output(success.command, task):
        issues.append(
            TaskLintIssue(
                "mutable-expected-output",
                "The grader references an expected, golden, or snapshot file inside the agent-writable workspace.",
            )
        )

    allowed = set(task.allowed_tools)
    if task.solution_commands and allowed and "shell" not in allowed:
        issues.append(
            TaskLintIssue(
                "solution-tool-bypass",
                "solution.commands uses shell outside the declared allowed_tools surface.",
            )
        )
    bypass_tools = sorted(
        {
            str(call.get("tool", ""))
            for call in task.solution_tool_calls
            if allowed and str(call.get("tool", "")) not in allowed
        }
    )
    if bypass_tools:
        issues.append(
            TaskLintIssue(
                "solution-tool-bypass",
                "solution.tool_calls uses tools outside allowed_tools: " + ", ".join(bypass_tools),
            )
        )

    if success.command and any(_normal(command) == _normal(success.command) for command in task.setup):
        issues.append(
            TaskLintIssue(
                "setup-satisfies-success",
                "A setup command is identical to the success command and can satisfy the task before the agent runs.",
            )
        )
    return issues


def probe_task_baseline(task: Task, docker_image: str = "python:3.13-slim") -> list[TaskLintIssue]:
    with DockerSandbox(task, image=docker_image) as sandbox:
        shell = ShellTool(sandbox)
        context = _SetupContext(task)
        setup_results = []
        for command in task.setup:
            result = shell.run({"cmd": command}, context)
            setup_results.append(result)
            if result.exit_code != 0:
                return [
                    TaskLintIssue(
                        "setup-failure",
                        f"Setup command failed during lint probe with exit code {result.exit_code}: {command}",
                    )
                ]
        grade = Grader().grade(task, sandbox, setup_results)
    if grade.passed:
        code = "setup-satisfies-success" if task.setup else "grader-passes-without-agent"
        return [
            TaskLintIssue(
                code,
                "The success criteria pass on the baseline workspace before any agent action.",
            )
        ]
    return []


def _weak_grader_reason(task: Task) -> str | None:
    success = task.success
    if success.type == "file_exists":
        return "file_exists only proves that a path exists, not that its content is correct."
    if success.type == "file_contains":
        return "file_contains accepts arbitrary surrounding content and needs stronger rejection checks."
    if success.type != "command" or not success.command:
        return None
    command = success.command.strip()
    if re.fullmatch(r"test\s+-[ef]\s+\S+", command):
        return "The success command checks only for path existence."
    grep = re.search(r"\bgrep\s+-q\s+(['\"]?)([^|;&]+?)\1(?:\s+\S+)?$", command)
    if grep and "grep -qx" not in command and not ("^" in grep.group(2) and "$" in grep.group(2)):
        return "The success command uses an unanchored grep that can accept extra or misleading content."
    return None


def _references_mutable_expected_output(command: str, task: Task) -> bool:
    allowed_tools = set(task.allowed_tools) if task.allowed_tools else {"shell", "file_write", "python"}
    if not allowed_tools.intersection({"shell", "file_write", "python"}):
        return False
    for path in task.workspace.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if not (name.startswith("expected") or name.startswith("golden") or name.startswith("snapshot")):
            continue
        relative = str(path.relative_to(task.workspace))
        if relative in command or path.name in command:
            return True
    return False


def _normal(command: str) -> str:
    return " ".join(command.split())


class _SetupContext:
    def __init__(self, task: Task) -> None:
        self.task = task
        self.tools_agent_name = "setup-lint"
        self.tool_results: list[object] = []
        self.recorder = _NullRecorder()


class _NullRecorder:
    def record(self, *args: object, **kwargs: object) -> dict[str, object]:
        return {}
