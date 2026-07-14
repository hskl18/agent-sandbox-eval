from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agent_sandbox_eval.version import TRAJECTORY_SCHEMA_VERSION


class TrajectoryRecorder:
    def __init__(self, path: Path, run_id: str, normalize_timestamps: bool = False) -> None:
        self.path = path
        self.run_id = run_id
        self.normalize_timestamps = normalize_timestamps
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
            "timestamp": self._timestamp(),
        }
        event.update({key: value for key, value in fields.items() if value is not None})
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, sort_keys=True) + "\n")
        self.step_index += 1
        return event

    def _timestamp(self) -> str:
        if self.normalize_timestamps:
            return (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=self.step_index)).isoformat()
        return datetime.now(UTC).isoformat()
