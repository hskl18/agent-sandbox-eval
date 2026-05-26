from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.extensions import load_task_pack_roots


def discover_task_files(root: Path = Path("benchmarks"), benchmark: str | None = None) -> list[Path]:
    if not root.exists():
        return []
    pattern = "**/task.yaml" if benchmark is None else f"{benchmark}/**/task.yaml"
    return sorted(root.glob(pattern))


def discover_task_files_many(roots: list[Path], benchmark: str | None = None) -> list[Path]:
    paths: list[Path] = []
    for root in roots:
        paths.extend(discover_task_files(root, benchmark))
    return sorted(paths)


def benchmark_roots(root: Path = Path("benchmarks"), include_task_packs: bool = True) -> list[Path]:
    roots = [root]
    if include_task_packs:
        for loaded in load_task_pack_roots().values():
            roots.extend(_coerce_roots(loaded))
    unique: list[Path] = []
    seen = set()
    for candidate in roots:
        resolved = candidate.resolve()
        if resolved not in seen:
            unique.append(candidate)
            seen.add(resolved)
    return unique


def load_task(path: Path) -> Task:
    path = path.resolve()
    with path.open("r", encoding="utf-8") as file:
        data: Any = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"task manifest must be a mapping: {path}")
    task = Task.from_dict(data, path)
    if not task.workspace.exists():
        raise ValueError(f"workspace does not exist for task {task.id}: {task.workspace}")
    return task


def load_benchmark(benchmark: str, root: Path = Path("benchmarks")) -> list[Task]:
    benchmark_filter = None if benchmark == "all" else benchmark
    tasks = [
        load_task(path)
        for path in discover_task_files_many(benchmark_roots(root), benchmark_filter)
    ]
    if not tasks:
        raise ValueError(f"no tasks found for benchmark: {benchmark}")
    return tasks


def _coerce_roots(value: Any) -> list[Path]:
    if isinstance(value, (str, Path)):
        return [Path(value)]
    if isinstance(value, list | tuple):
        return [Path(item) for item in value]
    raise TypeError("task pack entry point must return a path or list of paths")
