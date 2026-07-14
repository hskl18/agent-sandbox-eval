from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.version import BENCHMARK_SPLIT_SCHEMA_VERSION


@dataclass(frozen=True)
class BenchmarkSplit:
    schema_version: int
    id: str
    benchmark: str
    include_task_ids: list[str] = field(default_factory=list)
    exclude_task_ids: list[str] = field(default_factory=list)
    include_tags: list[str] = field(default_factory=list)
    exclude_tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkSplit":
        schema_version = int(data.get("schema_version", 0))
        if schema_version != BENCHMARK_SPLIT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported benchmark split schema_version {schema_version}; "
                f"expected {BENCHMARK_SPLIT_SCHEMA_VERSION}"
            )
        split_id = str(data.get("id", "")).strip()
        benchmark = str(data.get("benchmark", "")).strip()
        if not split_id:
            raise ValueError("benchmark split id is required")
        if not benchmark:
            raise ValueError("benchmark split benchmark is required")
        return cls(
            schema_version=schema_version,
            id=split_id,
            benchmark=benchmark,
            include_task_ids=_string_list(data, "include_task_ids"),
            exclude_task_ids=_string_list(data, "exclude_task_ids"),
            include_tags=_string_list(data, "include_tags"),
            exclude_tags=_string_list(data, "exclude_tags"),
        )


def discover_splits(root: Path = Path("benchmarks")) -> list[Path]:
    split_root = root / "splits"
    if not split_root.exists():
        return []
    return sorted(split_root.glob("*.yaml"))


def load_split(split: str, root: Path = Path("benchmarks")) -> BenchmarkSplit:
    path = root / "splits" / f"{split}.yaml"
    if not path.exists():
        raise ValueError(f"benchmark split not found: {split}")
    with path.open("r", encoding="utf-8") as file:
        data: Any = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"benchmark split must be a mapping: {path}")
    loaded = BenchmarkSplit.from_dict(data)
    if loaded.id != split:
        raise ValueError(f"benchmark split id {loaded.id!r} does not match filename {split!r}")
    return loaded


def apply_split(tasks: list[Task], split: BenchmarkSplit) -> list[Task]:
    benchmark_tasks = [
        task for task in tasks if split.benchmark == "all" or task.benchmark == split.benchmark
    ]
    known_ids = {task.id for task in benchmark_tasks}
    unknown_ids = sorted(set(split.include_task_ids + split.exclude_task_ids) - known_ids)
    if unknown_ids:
        raise ValueError(f"benchmark split {split.id} references unknown tasks: {', '.join(unknown_ids)}")

    selected = benchmark_tasks
    if split.include_task_ids:
        included = set(split.include_task_ids)
        selected = [task for task in selected if task.id in included]
    if split.include_tags:
        included_tags = set(split.include_tags)
        selected = [task for task in selected if included_tags.intersection(task.tags)]
    excluded_ids = set(split.exclude_task_ids)
    excluded_tags = set(split.exclude_tags)
    selected = [
        task
        for task in selected
        if task.id not in excluded_ids and not excluded_tags.intersection(task.tags)
    ]
    if not selected:
        raise ValueError(f"benchmark split selected no tasks: {split.id}")
    return sorted(selected, key=lambda task: (task.benchmark, task.id))


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"benchmark split {key} must be a list of non-empty strings")
    return [item.strip() for item in value]
