from __future__ import annotations

from typing import Any

from agent_sandbox_eval.sandbox.docker import DockerSandbox
from agent_sandbox_eval.tools.base import ToolResult


class PythonTool:
    name = "python"
    description = "Run a Python snippet inside the task sandbox."

    def __init__(self, sandbox: DockerSandbox) -> None:
        self.sandbox = sandbox

    def run(self, input: dict[str, Any], context: Any) -> ToolResult:
        code = str(input.get("code", ""))
        command = "python - <<'PY'\n" + code + "\nPY"
        context.recorder.record("tool_call", context.task.id, tool=self.name, input={"code": code})
        result = self.sandbox.run(command, timeout_seconds=context.task.limits.timeout_seconds)
        if hasattr(context, "tool_results"):
            context.tool_results.append(result)
        context.recorder.record("tool_result", context.task.id, tool=self.name, input={"code": code}, output=result.to_dict())
        return result
