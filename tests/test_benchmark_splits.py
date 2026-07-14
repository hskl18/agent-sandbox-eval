from pathlib import Path

import pytest

from agent_sandbox_eval.benchmarks.loader import load_benchmark
from agent_sandbox_eval.benchmarks.splits import BenchmarkSplit, apply_split, load_split


def test_smoke_split_selects_one_task_per_benchmark() -> None:
    tasks = load_benchmark("all", Path("benchmarks"))

    selected = apply_split(tasks, load_split("smoke", Path("benchmarks")))

    assert [task.id for task in selected] == [
        "update-status-001",
        "fix-python-function-001",
        "pass-command-001",
    ]


def test_split_rejects_unknown_task_ids() -> None:
    tasks = load_benchmark("terminal", Path("benchmarks"))
    split = BenchmarkSplit(
        schema_version=1,
        id="bad",
        benchmark="terminal",
        include_task_ids=["missing-task"],
    )

    with pytest.raises(ValueError, match="unknown tasks"):
        apply_split(tasks, split)
