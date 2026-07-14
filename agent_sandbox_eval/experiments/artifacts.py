from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_sandbox_eval.trajectories.replay import iter_events
from agent_sandbox_eval.version import TRAJECTORY_SCHEMA_VERSION


class ArtifactValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AttemptArtifact:
    marker: dict[str, Any]
    raw_path: Path | None
    events: list[dict[str, Any]]


def canonical_json(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def write_atomic_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical_json(data), encoding="utf-8")
    os.replace(temporary, path)


def ensure_config_snapshot(root: Path, snapshot: dict[str, object]) -> Path:
    path = root / "experiment.snapshot.json"
    expected = canonical_json(snapshot)
    if path.exists():
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            raise ArtifactValidationError(
                f"artifact root belongs to a different experiment configuration: {path}"
            )
    else:
        root.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_trajectory(
    path: Path,
    expected_run_id: str,
    expected_task_id: str,
    require_complete: bool,
) -> list[dict[str, Any]]:
    if not path.exists():
        raise ArtifactValidationError(f"raw trajectory is missing: {path}")
    try:
        events = iter_events(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"raw trajectory is unreadable: {path}: {exc}") from exc
    if not events:
        raise ArtifactValidationError(f"raw trajectory is empty: {path}")
    for expected_step, event in enumerate(events):
        if event.get("schema_version") != TRAJECTORY_SCHEMA_VERSION:
            raise ArtifactValidationError(
                f"raw trajectory has unsupported schema at step {expected_step}: {path}"
            )
        if event.get("run_id") != expected_run_id:
            raise ArtifactValidationError(
                f"raw trajectory run_id mismatch at step {expected_step}: {path}"
            )
        if event.get("step_index") != expected_step:
            raise ArtifactValidationError(
                f"raw trajectory step sequence is not contiguous at step {expected_step}: {path}"
            )
        task_id = event.get("task_id")
        if task_id is not None and task_id != expected_task_id:
            raise ArtifactValidationError(
                f"raw trajectory contains unexpected task {task_id!r}: {path}"
            )
    if require_complete:
        run_starts = [event for event in events if event.get("event_type") == "run_start"]
        run_ends = [event for event in events if event.get("event_type") == "run_end"]
        grades = [event for event in events if event.get("event_type") == "grader_result"]
        if len(run_starts) != 1 or len(run_ends) != 1 or len(grades) != 1:
            raise ArtifactValidationError(
                "raw trajectory must contain exactly one run_start, run_end, and grader_result: "
                f"{path}"
            )
        last_boundary = events[-1].get("event_type")
        if last_boundary == "attempt_result" and len(events) >= 2:
            last_boundary = events[-2].get("event_type")
        if events[0].get("event_type") != "run_start" or last_boundary != "run_end":
            raise ArtifactValidationError(f"raw trajectory has incomplete event boundaries: {path}")
    return events


def read_attempt_marker(path: Path, root: Path) -> AttemptArtifact:
    if not path.exists():
        raise ArtifactValidationError(f"attempt marker is missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"attempt marker is unreadable: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ArtifactValidationError(f"attempt marker must contain an object: {path}")
    required = {
        "run_id",
        "cell_id",
        "task_id",
        "trial",
        "attempt",
        "status",
        "failure_scope",
        "retry_eligible",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ArtifactValidationError(f"attempt marker is missing fields {', '.join(missing)}: {path}")
    raw_relative = data.get("raw_path")
    if raw_relative is None:
        if data.get("status") != "runner_error":
            raise ArtifactValidationError(f"non-runner attempt has no raw trajectory: {path}")
        return AttemptArtifact(marker=data, raw_path=None, events=[])
    raw_path = (root / str(raw_relative)).resolve()
    if root.resolve() not in raw_path.parents:
        raise ArtifactValidationError(f"attempt raw_path escapes the artifact root: {path}")
    expected_name = path.name.removesuffix(".attempt.json") + ".jsonl"
    expected_raw_path = path.with_name(expected_name).resolve()
    if raw_path != expected_raw_path:
        raise ArtifactValidationError(
            f"attempt marker references an unexpected raw trajectory: {path}: {raw_path}"
        )
    expected_hash = data.get("raw_sha256")
    actual_hash = sha256_file(raw_path) if raw_path.exists() else None
    if actual_hash != expected_hash:
        raise ArtifactValidationError(
            f"raw trajectory hash mismatch or missing file for marker {path}: {raw_path}"
        )
    events = validate_trajectory(
        raw_path,
        expected_run_id=str(data["run_id"]),
        expected_task_id=str(data["task_id"]),
        require_complete=data.get("status") != "runner_error",
    )
    return AttemptArtifact(marker=data, raw_path=raw_path, events=events)
