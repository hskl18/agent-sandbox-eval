from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def iter_events(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def replay_trajectory(path: Path, task_id: str | None = None) -> str:
    lines: list[str] = []
    for event in iter_events(path):
        if task_id and event.get("task_id") != task_id:
            continue
        event_type = event.get("event_type")
        task = event.get("task_id") or "-"
        prefix = f"[{event.get('step_index')}] {task} {event_type}"
        if event_type == "tool_call":
            lines.append(f"{prefix}: {event.get('tool')} {event.get('input')}")
        elif event_type == "tool_result":
            output = event.get("output") or {}
            lines.append(f"{prefix}: exit={output.get('exit_code')} stdout={output.get('stdout', '').strip()!r}")
        elif event_type == "grader_result":
            lines.append(f"{prefix}: passed={event.get('passed')} failure={event.get('failure_mode')}")
        else:
            detail = event.get("message") or event.get("final_answer") or ""
            lines.append(f"{prefix}: {detail}")
    return "\n".join(lines)

