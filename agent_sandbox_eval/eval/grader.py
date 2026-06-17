from __future__ import annotations

import json
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
        elif task.success.type == "json_fields" and task.success.path and task.success.json_fields:
            command = _json_fields_command(task.success.path, task.success.json_fields)
            raw = sandbox.run(command, timeout_seconds=task.limits.timeout_seconds)
            evidence = [
                f"Required JSON file: {task.success.path}",
                f"Required JSON fields: {', '.join(sorted(task.success.json_fields))}",
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


def _json_fields_command(path: str, fields: dict[str, object]) -> str:
    path_json = json.dumps(path)
    fields_json = json.dumps(fields, sort_keys=True)
    return (
        "python - <<'PY'\n"
        "import json\n"
        "from pathlib import Path\n"
        f"path = {path_json}\n"
        f"expected = {fields_json}\n"
        "data = json.loads(Path(path).read_text(encoding='utf-8'))\n"
        "\n"
        "def resolve(value, selector):\n"
        "    current = value\n"
        "    for part in selector.split('.'):\n"
        "        if isinstance(current, list):\n"
        "            current = current[int(part)]\n"
        "        else:\n"
        "            current = current[part]\n"
        "    return current\n"
        "\n"
        "mismatches = []\n"
        "for selector, expected_value in expected.items():\n"
        "    try:\n"
        "        actual_value = resolve(data, selector)\n"
        "    except (KeyError, IndexError, TypeError, ValueError) as exc:\n"
        "        mismatches.append({'field': selector, 'error': str(exc)})\n"
        "        continue\n"
        "    if actual_value != expected_value:\n"
        "        mismatches.append({'field': selector, 'expected': expected_value, 'actual': actual_value})\n"
        "if mismatches:\n"
        "    print(json.dumps(mismatches, sort_keys=True))\n"
        "    raise SystemExit(1)\n"
        "PY"
    )
