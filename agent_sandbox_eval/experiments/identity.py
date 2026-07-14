from __future__ import annotations

import hashlib
import inspect
import json
import os
import platform
import stat
from dataclasses import dataclass
from pathlib import Path

from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.benchmarks.splits import BenchmarkSplit
from agent_sandbox_eval.experiments.schema import ExperimentSpec
from agent_sandbox_eval.extensions import list_all_entry_points
from agent_sandbox_eval.version import package_version


@dataclass(frozen=True)
class ExperimentIdentity:
    fingerprint: str
    snapshot: dict[str, object]


def resolve_experiment_identity(
    spec: ExperimentSpec,
    tasks: list[Task],
    benchmark_split: BenchmarkSplit,
    attempt_executor: object,
) -> ExperimentIdentity:
    if benchmark_split.id != spec.benchmark.split:
        raise ValueError(
            f"benchmark split id {benchmark_split.id!r} does not match experiment split "
            f"{spec.benchmark.split!r}"
        )
    if benchmark_split.benchmark not in {"all", spec.benchmark.name}:
        raise ValueError(
            f"benchmark split {benchmark_split.id!r} targets {benchmark_split.benchmark!r}, "
            f"not {spec.benchmark.name!r}"
        )
    resolved_inputs: dict[str, object] = {
        "experiment": spec.to_dict(),
        "benchmark_split": benchmark_split.to_dict(),
        "tasks": [_task_identity(task) for task in sorted(tasks, key=lambda item: (item.benchmark, item.id))],
        "implementation": _implementation_identity(attempt_executor),
    }
    fingerprint = _json_sha256(resolved_inputs)[:16]
    return ExperimentIdentity(
        fingerprint=fingerprint,
        snapshot={
            "schema_version": 1,
            "fingerprint": fingerprint,
            "resolved_inputs": resolved_inputs,
        },
    )


def _task_identity(task: Task) -> dict[str, object]:
    manifest_sha256 = _file_sha256(task.manifest_path) if task.manifest_path.is_file() else None
    success = task.success
    limits = task.limits
    return {
        "schema_version": task.schema_version,
        "id": task.id,
        "benchmark": task.benchmark,
        "title": task.title,
        "instruction": task.instruction,
        "manifest_sha256": manifest_sha256,
        "success": {
            "type": success.type,
            "command": success.command,
            "expected_exit_code": success.expected_exit_code,
            "path": success.path,
            "contains": success.contains,
            "json_fields": success.json_fields,
            "negative_assertions": success.negative_assertions,
        },
        "setup": task.setup,
        "allowed_tools": task.allowed_tools,
        "limits": {
            "timeout_seconds": limits.timeout_seconds,
            "max_tool_calls": limits.max_tool_calls,
            "memory_mb": limits.memory_mb,
            "cpus": limits.cpus,
            "pids_limit": limits.pids_limit,
            "network": limits.network,
        },
        "tags": task.tags,
        "solution_commands": task.solution_commands,
        "solution_tool_calls": task.solution_tool_calls,
        "workspace": _workspace_identity(task.workspace),
    }


def _workspace_identity(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(os.lstat(path).st_mode)
        if path.is_symlink():
            entries.append(
                {"path": relative, "type": "symlink", "mode": mode, "target": os.readlink(path)}
            )
        elif path.is_dir():
            entries.append({"path": relative, "type": "directory", "mode": mode})
        elif path.is_file():
            entries.append(
                {"path": relative, "type": "file", "mode": mode, "sha256": _file_sha256(path)}
            )
        else:
            entries.append({"path": relative, "type": "other", "mode": mode})
    return entries


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _implementation_identity(attempt_executor: object) -> dict[str, object]:
    package_root = Path(__file__).resolve().parents[1]
    core_files = [
        {"path": path.relative_to(package_root).as_posix(), "sha256": _file_sha256(path)}
        for path in sorted(package_root.rglob("*.py"))
    ]
    executor_target = attempt_executor if inspect.isfunction(attempt_executor) else type(attempt_executor)
    executor_source = inspect.getsourcefile(executor_target)
    executor_path = Path(executor_source).resolve() if executor_source else None
    executor_identity: dict[str, object] = {
        "module": getattr(executor_target, "__module__", type(attempt_executor).__module__),
        "qualname": getattr(executor_target, "__qualname__", type(attempt_executor).__qualname__),
        "source_sha256": (
            _file_sha256(executor_path) if executor_path is not None and executor_path.is_file() else None
        ),
    }
    extensions: list[dict[str, object]] = []
    for group, entry_points in sorted(list_all_entry_points().items()):
        for entry_point in sorted(
            entry_points,
            key=lambda item: (item.name, item.value, item.distribution or "", item.version or ""),
        ):
            extensions.append(
                {
                    "group": group,
                    "name": entry_point.name,
                    "value": entry_point.value,
                    "distribution": entry_point.distribution,
                    "version": entry_point.version,
                }
            )
    return {
        "package": "agent-sandbox-eval",
        "package_version": package_version(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "core_files": core_files,
        "attempt_executor": executor_identity,
        "extensions": extensions,
    }


def _json_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
