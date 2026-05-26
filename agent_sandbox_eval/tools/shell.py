from __future__ import annotations

from typing import Any

from agent_sandbox_eval.sandbox.docker import DockerSandbox
from agent_sandbox_eval.tools.base import ToolResult


class ShellTool:
    name = "shell"
    description = "Run a shell command inside the task sandbox."

    def __init__(self, sandbox: DockerSandbox) -> None:
        self.sandbox = sandbox

    def run(self, input: dict[str, Any], context: Any) -> ToolResult:
        command = str(input.get("cmd", "")).strip()
        if not command:
            raise ValueError("shell tool requires input.cmd")
        context.recorder.record(
            "tool_call",
            context.task.id,
            agent=context.tools_agent_name if hasattr(context, "tools_agent_name") else None,
            tool=self.name,
            input={"cmd": command},
        )
        result = self.sandbox.run(command, timeout_seconds=context.task.limits.timeout_seconds)
        if hasattr(context, "tool_results"):
            context.tool_results.append(result)
        context.recorder.record(
            "tool_result",
            context.task.id,
            agent=context.tools_agent_name if hasattr(context, "tools_agent_name") else None,
            tool=self.name,
            input={"cmd": command},
            output=result.to_dict(),
            duration_ms=result.duration_ms,
        )
        return result
