from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agent_sandbox_eval.reports.markdown import summarize_trajectory
from agent_sandbox_eval.trajectories.recorder import TrajectoryRecorder
from tools import build_harness_manifest


def _write_control_trajectory(path: Path, agent: str, pass_count: int) -> None:
    recorder = TrajectoryRecorder(path, f"{agent}-control", normalize_timestamps=True)
    recorder.record("run_start", agent=agent, task_count=25)
    for index in range(25):
        task_id = f"task-{index:02d}"
        passed = index < pass_count
        recorder.record("task_start", task_id, agent=agent)
        recorder.record(
            "grader_result",
            task_id,
            agent=agent,
            passed=passed,
            score=1.0 if passed else 0.0,
            failure_mode=None if passed else "no_progress",
            evidence=[],
            raw_result={"duration_ms": 1},
        )
    recorder.record("run_end", agent=agent, passed_tasks=pass_count, total_tasks=25)


def _write_noop_trajectory(path: Path) -> None:
    _write_control_trajectory(path, "noop", 0)


def _control_inputs(tmp_path: Path, pass_counts: tuple[int, int, int]) -> dict[str, Path]:
    inputs = {
        "scripted": tmp_path / "scripted.jsonl",
        "react-local-solution": tmp_path / "react.jsonl",
        "noop": tmp_path / "noop.jsonl",
    }
    agents = {"scripted": "scripted", "react-local-solution": "react", "noop": "noop"}
    for (label, path), pass_count in zip(inputs.items(), pass_counts, strict=True):
        _write_control_trajectory(path, agents[label], pass_count)
    return inputs


def test_manifest_builder_rejects_identical_noop_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trajectory = tmp_path / "noop.jsonl"
    output = tmp_path / "manifest.json"
    _write_noop_trajectory(trajectory)

    monkeypatch.setattr(build_harness_manifest, "_docker_version", lambda: "test")
    monkeypatch.setattr(build_harness_manifest, "_git_commit", lambda: "0" * 40)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_harness_manifest.py",
            "--scripted",
            str(trajectory),
            "--react-local-solution",
            str(trajectory),
            "--noop",
            str(trajectory),
            "--out",
            str(output),
        ],
    )

    with pytest.raises(ValueError, match="distinct control trajectories"):
        build_harness_manifest.main()
    assert not output.exists()


def test_manifest_semantic_controls_accept_25_25_0(tmp_path: Path) -> None:
    inputs = _control_inputs(tmp_path, (25, 25, 0))
    summaries = {label: summarize_trajectory(path) for label, path in inputs.items()}

    build_harness_manifest._validate_control_runs(inputs, summaries)


@pytest.mark.parametrize(
    ("pass_counts", "message"),
    [
        ((24, 25, 0), "scripted oracle"),
        ((25, 24, 0), "ReAct local-solution"),
        ((25, 25, 1), "noop negative control"),
    ],
)
def test_manifest_semantic_controls_reject_incorrect_pass_counts(
    tmp_path: Path,
    pass_counts: tuple[int, int, int],
    message: str,
) -> None:
    inputs = _control_inputs(tmp_path, pass_counts)
    summaries = {label: summarize_trajectory(path) for label, path in inputs.items()}

    with pytest.raises(ValueError, match=message):
        build_harness_manifest._validate_control_runs(inputs, summaries)
