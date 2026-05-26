from __future__ import annotations

from dataclasses import dataclass

from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.eval.failure_analysis import analyze_failure
from agent_sandbox_eval.sandbox.docker import DockerSandbox
from agent_sandbox_eval.tools.base import ToolResult


@dataclass(frozen=True)
class GraderResult:
    task_id: str
    passed: bool
    score: float
    failure_mode: str | None
    evidence: list[str]
    raw_result: ToolResult


class Grader:
    def grade(self, task: Task, sandbox: DockerSandbox, agent_tool_results: list[ToolResult]) -> GraderResult:
        if task.success.type == "command" and task.success.command:
            raw = sandbox.run(task.success.command, timeout_seconds=task.limits.timeout_seconds)
            evidence = [
                f"Success command: {task.success.command}",
                f"Expected exit code: {task.success.expected_exit_code}",
                f"Actual exit code: {raw.exit_code}",
            ]
            passed = raw.exit_code == task.success.expected_exit_code
        elif task.success.type == "file_exists" and task.success.path:
            raw = sandbox.run(f"test -f {task.success.path}", timeout_seconds=task.limits.timeout_seconds)
            evidence = [f"Required file: {task.success.path}", f"Actual exit code: {raw.exit_code}"]
            passed = raw.exit_code == 0
        elif task.success.type == "file_contains" and task.success.path and task.success.contains is not None:
            command = (
                "python - <<'PY'\n"
                f"from pathlib import Path\n"
                f"text = Path({task.success.path!r}).read_text(encoding='utf-8')\n"
                f"needle = {task.success.contains!r}\n"
                "raise SystemExit(0 if needle in text else 1)\n"
                "PY"
            )
            raw = sandbox.run(command, timeout_seconds=task.limits.timeout_seconds)
            evidence = [
                f"Required file: {task.success.path}",
                f"Required content: {task.success.contains}",
                f"Actual exit code: {raw.exit_code}",
            ]
            passed = raw.exit_code == 0
        else:
            raise ValueError(f"unsupported success criteria for task {task.id}: {task.success.type}")
        if raw.stdout.strip():
            evidence.append(f"stdout: {raw.stdout.strip()[:500]}")
        if raw.stderr.strip():
            evidence.append(f"stderr: {raw.stderr.strip()[:500]}")
        failure_mode = None
        if not passed:
            analysis = analyze_failure(agent_tool_results, raw, max_tool_calls=task.limits.max_tool_calls)
            failure_mode = analysis.failure_mode
            evidence.extend(analysis.evidence)
        return GraderResult(
            task_id=task.id,
            passed=passed,
            score=1.0 if passed else 0.0,
            failure_mode=failure_mode,
            evidence=evidence,
            raw_result=raw,
        )
