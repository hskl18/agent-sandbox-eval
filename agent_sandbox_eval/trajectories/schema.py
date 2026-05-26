from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_sandbox_eval.version import TRAJECTORY_SCHEMA_VERSION


@dataclass(frozen=True)
class TrajectoryEvent:
    run_id: str
    task_id: str | None
    step_index: int
    event_type: str
    timestamp: str
    schema_version: int = TRAJECTORY_SCHEMA_VERSION
    payload: dict[str, Any] = field(default_factory=dict)

