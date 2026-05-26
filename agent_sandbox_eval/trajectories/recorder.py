from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_sandbox_eval.version import TRAJECTORY_SCHEMA_VERSION


class TrajectoryRecorder:
    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.step_index = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def record(self, event_type: str, task_id: str | None = None, **fields: Any) -> dict[str, Any]:
        event = {
            "schema_version": TRAJECTORY_SCHEMA_VERSION,
            "run_id": self.run_id,
            "task_id": task_id,
            "step_index": self.step_index,
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        event.update({key: value for key, value in fields.items() if value is not None})
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, sort_keys=True) + "\n")
        self.step_index += 1
        return event
