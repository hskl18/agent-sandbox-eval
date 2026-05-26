from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_sandbox_eval.tools.base import ToolResult


class MCPStateTool:
    """Small JSON-backed MCP-like state tool for benchmark tasks."""

    name = "mcp_state"
    description = "Read or update JSON-backed task state through a tool interface."

    def __init__(self, workspace: Path, filename: str = "state.json") -> None:
        self.path = workspace / filename

    def run(self, input: dict[str, Any], context: Any) -> ToolResult:
        action = str(input.get("action", "get"))
        key = str(input.get("key", ""))
        state = self._read_state()
        context.recorder.record("tool_call", context.task.id, tool=self.name, input=input)

        if action == "get":
            payload = state.get(key) if key else state
        elif action == "set":
            if not key:
                raise ValueError("mcp_state set requires input.key")
            state[key] = input.get("value")
            self._write_state(state)
            payload = {"updated": key}
        else:
            raise ValueError(f"unsupported mcp_state action: {action}")

        result = ToolResult(stdout=json.dumps(payload, sort_keys=True))
        if hasattr(context, "tool_results"):
            context.tool_results.append(result)
        context.recorder.record("tool_result", context.task.id, tool=self.name, input=input, output=result.to_dict())
        return result

    def _read_state(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"state file must contain a JSON object: {self.path}")
        return data

    def _write_state(self, state: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
