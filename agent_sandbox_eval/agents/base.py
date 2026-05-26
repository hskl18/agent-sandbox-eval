from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.tools.base import Tool
from agent_sandbox_eval.trajectories.recorder import TrajectoryRecorder


@dataclass(frozen=True)
class AgentContext:
    task: Task
    tools: dict[str, Tool]
    recorder: TrajectoryRecorder


@dataclass(frozen=True)
class AgentResult:
    final_answer: str


class Agent(Protocol):
    name: str

    def run(self, context: AgentContext) -> AgentResult:
        ...

