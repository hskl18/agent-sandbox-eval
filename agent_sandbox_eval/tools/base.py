from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class ToolContext:
    task_id: str


class Tool(Protocol):
    name: str
    description: str

    def run(self, input: dict[str, Any], context: Any) -> ToolResult:
        ...

