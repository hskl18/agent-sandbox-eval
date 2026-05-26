from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_sandbox_eval.tools.base import ToolResult


class FileReadTool:
    name = "file_read"
    description = "Read a text file from the sandbox workspace snapshot."

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def run(self, input: dict[str, Any], context: Any) -> ToolResult:
        path = self._resolve(str(input.get("path", "")))
        text = path.read_text(encoding="utf-8")
        context.recorder.record("tool_call", context.task.id, tool=self.name, input=input)
        result = ToolResult(stdout=text)
        if hasattr(context, "tool_results"):
            context.tool_results.append(result)
        context.recorder.record("tool_result", context.task.id, tool=self.name, input=input, output=result.to_dict())
        return result

    def _resolve(self, path: str) -> Path:
        candidate = (self.workspace / path).resolve()
        if self.workspace.resolve() not in candidate.parents and candidate != self.workspace.resolve():
            raise ValueError(f"path escapes workspace: {path}")
        return candidate


class FileWriteTool:
    name = "file_write"
    description = "Write a text file in the sandbox workspace snapshot."

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def run(self, input: dict[str, Any], context: Any) -> ToolResult:
        path = self._resolve(str(input.get("path", "")))
        text = str(input.get("content", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        context.recorder.record("tool_call", context.task.id, tool=self.name, input={"path": input.get("path")})
        result = ToolResult(stdout=f"wrote {path.relative_to(self.workspace)}")
        if hasattr(context, "tool_results"):
            context.tool_results.append(result)
        context.recorder.record(
            "tool_result",
            context.task.id,
            tool=self.name,
            input={"path": input.get("path")},
            output=result.to_dict(),
        )
        return result

    def _resolve(self, path: str) -> Path:
        candidate = (self.workspace / path).resolve()
        if self.workspace.resolve() not in candidate.parents and candidate != self.workspace.resolve():
            raise ValueError(f"path escapes workspace: {path}")
        return candidate
