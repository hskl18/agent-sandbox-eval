from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_sandbox_eval.version import TASK_SCHEMA_VERSION


@dataclass(frozen=True)
class Limits:
    timeout_seconds: int = 120
    max_tool_calls: int = 30
    memory_mb: int = 1024
    cpus: float = 1.0
    network: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Limits":
        data = data or {}
        limits = cls(
            timeout_seconds=int(data.get("timeout_seconds", 120)),
            max_tool_calls=int(data.get("max_tool_calls", 30)),
            memory_mb=int(data.get("memory_mb", 1024)),
            cpus=float(data.get("cpus", 1.0)),
            network=bool(data.get("network", False)),
        )
        if limits.timeout_seconds <= 0:
            raise ValueError("limits.timeout_seconds must be positive")
        if limits.max_tool_calls <= 0:
            raise ValueError("limits.max_tool_calls must be positive")
        if limits.memory_mb <= 0:
            raise ValueError("limits.memory_mb must be positive")
        if limits.cpus <= 0:
            raise ValueError("limits.cpus must be positive")
        return limits


@dataclass(frozen=True)
class SuccessCriteria:
    type: str
    command: str | None = None
    expected_exit_code: int = 0
    path: str | None = None
    contains: str | None = None
    json_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SuccessCriteria":
        success_type = str(data.get("type", "")).strip()
        if not success_type:
            raise ValueError("success.type is required")
        if success_type == "command" and not data.get("command"):
            raise ValueError("success.command is required for command checks")
        if success_type == "file_exists" and not data.get("path"):
            raise ValueError("success.path is required for file_exists checks")
        if success_type == "file_contains" and (not data.get("path") or data.get("contains") is None):
            raise ValueError("success.path and success.contains are required for file_contains checks")
        if success_type == "json_fields":
            if not data.get("path"):
                raise ValueError("success.path is required for json_fields checks")
            fields = data.get("fields")
            if not isinstance(fields, dict) or not fields:
                raise ValueError("success.fields must be a non-empty mapping for json_fields checks")
        if success_type not in {"command", "file_exists", "file_contains", "json_fields"}:
            raise ValueError(f"unsupported success.type: {success_type}")
        return cls(
            type=success_type,
            command=data.get("command"),
            expected_exit_code=int(data.get("expected_exit_code", 0)),
            path=data.get("path"),
            contains=data.get("contains"),
            json_fields=dict(data.get("fields") or {}),
        )


@dataclass(frozen=True)
class Task:
    schema_version: int
    id: str
    benchmark: str
    title: str
    instruction: str
    workspace: Path
    manifest_path: Path
    success: SuccessCriteria
    setup: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    limits: Limits = field(default_factory=Limits)
    tags: list[str] = field(default_factory=list)
    solution_commands: list[str] = field(default_factory=list)
    solution_tool_calls: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any], manifest_path: Path) -> "Task":
        required = ["schema_version", "id", "benchmark", "title", "instruction", "workspace", "success"]
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"missing required task fields: {', '.join(missing)}")
        schema_version = int(data["schema_version"])
        if schema_version != TASK_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported task schema_version {schema_version}; expected {TASK_SCHEMA_VERSION}"
            )

        workspace = Path(str(data["workspace"]))
        if not workspace.is_absolute():
            workspace = manifest_path.parent / workspace

        solution = data.get("solution") or {}
        if not isinstance(solution, dict):
            raise ValueError("solution must be a mapping when provided")
        solution_tool_calls = solution.get("tool_calls", [])
        if not isinstance(solution_tool_calls, list):
            raise ValueError("solution.tool_calls must be a list when provided")
        for call in solution_tool_calls:
            if not isinstance(call, dict) or "tool" not in call or "input" not in call:
                raise ValueError("each solution.tool_calls entry must contain tool and input")
            if not isinstance(call["input"], dict):
                raise ValueError("solution.tool_calls input must be a mapping")
        allowed_tools = [str(tool) for tool in data.get("allowed_tools", [])]
        solution_commands = [str(command) for command in solution.get("commands", [])]
        if allowed_tools:
            if solution_commands and "shell" not in allowed_tools:
                raise ValueError("solution.commands require shell to be listed in allowed_tools")
            disallowed_solution_tools = sorted(
                {
                    str(call["tool"])
                    for call in solution_tool_calls
                    if str(call["tool"]) not in allowed_tools
                }
            )
            if disallowed_solution_tools:
                raise ValueError(
                    "solution.tool_calls reference tools outside allowed_tools: "
                    + ", ".join(disallowed_solution_tools)
                )
        return cls(
            schema_version=schema_version,
            id=str(data["id"]),
            benchmark=str(data["benchmark"]),
            title=str(data["title"]),
            instruction=str(data["instruction"]).strip(),
            workspace=workspace,
            manifest_path=manifest_path,
            setup=[str(command) for command in data.get("setup", [])],
            allowed_tools=allowed_tools,
            success=SuccessCriteria.from_dict(data["success"]),
            limits=Limits.from_dict(data.get("limits")),
            tags=[str(tag) for tag in data.get("tags", [])],
            solution_commands=solution_commands,
            solution_tool_calls=list(solution_tool_calls),
        )
