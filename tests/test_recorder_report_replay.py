import json
from pathlib import Path

from agent_sandbox_eval.reports.markdown import build_comparison_report, build_markdown_report, summarize_trajectory
from agent_sandbox_eval.trajectories.recorder import TrajectoryRecorder
from agent_sandbox_eval.trajectories.replay import replay_trajectory


def test_recorder_writes_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    recorder = TrajectoryRecorder(path, "test-run")
    recorder.record("task_start", "task-1", message="start")
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["schema_version"] == 1
    assert events[0]["run_id"] == "test-run"
    assert events[0]["event_type"] == "task_start"


def test_replay_and_report(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    recorder = TrajectoryRecorder(path, "test-run")
    recorder.record("task_start", "task-1", success_command="true")
    recorder.record("tool_call", "task-1", tool="shell", input={"cmd": "true"})
    recorder.record(
        "tool_result",
        "task-1",
        tool="shell",
        output={"exit_code": 0, "stdout": "", "stderr": "", "duration_ms": 5},
    )
    recorder.record(
        "model_call",
        "task-1",
        provider="test-provider",
        model="test-model",
        input_tokens=120,
        output_tokens=30,
        estimated_cost_usd=0.00048,
    )
    recorder.record("grader_result", "task-1", passed=True, score=1.0, raw_result={"duration_ms": 1})
    recorder.record("run_end", agent="test-agent", passed_tasks=1, total_tasks=1)

    replay = replay_trajectory(path, task_id="task-1")
    report = build_markdown_report(path)
    summary = summarize_trajectory(path)
    comparison = build_comparison_report([path])

    assert "tool_call" in replay
    assert "Pass rate: 100.0%" in report
    assert "Average score: 1.00" in report
    assert "Average tool calls per task: 1.0" in report
    assert "Verification rate: 100.0%" in report
    assert "Model calls: 1" in report
    assert "Input tokens: 120" in report
    assert "Estimated model cost: $0.000480" in report
    assert "## Tool Use" in report
    assert "`shell`: 1" in report
    assert summary["agent"] == "test-agent"
    assert summary["average_score"] == 1.0
    assert summary["model_calls"] == 1
    assert summary["input_tokens"] == 120
    assert summary["estimated_cost_usd"] == 0.00048
    assert "| test-agent | 1 | 100.0%" in comparison


def test_report_includes_failure_evidence(tmp_path: Path) -> None:
    path = tmp_path / "failed.jsonl"
    recorder = TrajectoryRecorder(path, "test-run")
    recorder.record(
        "grader_result",
        "task-1",
        passed=False,
        score=0.0,
        failure_mode="no_progress",
        evidence=["Agent tool calls: 0", "Final grader exit code: 1"],
        raw_result={"duration_ms": 1},
    )
    recorder.record("run_end", agent="test-agent", passed_tasks=0, total_tasks=1)

    report = build_markdown_report(path)

    assert "## Failure Evidence" in report
    assert "Agent tool calls: 0" in report
