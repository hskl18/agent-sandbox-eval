from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from agent_sandbox_eval.benchmarks.schema import Task


@dataclass(frozen=True)
class AgentAction:
    kind: str
    tool: str | None = None
    input: dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass(frozen=True)
class StepContext:
    step_index: int
    observations: list[dict[str, Any]] = field(default_factory=list)


class ModelProvider(Protocol):
    name: str

    def plan(self, task: Task) -> list[str]:
        ...

    def actions(self, task: Task) -> list[AgentAction]:
        ...

    def next_action(self, task: Task, context: StepContext) -> AgentAction:
        ...
