from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.experiments.artifacts import ArtifactValidationError
from agent_sandbox_eval.experiments.metrics import empirical_pass_at_k, empirical_pass_power_k
from agent_sandbox_eval.experiments.runner import (
    AttemptContext,
    AttemptObservation,
    regenerate_matrix_reports,
    run_matrix,
)
from agent_sandbox_eval.experiments.schema import ExperimentSpec, PricingSpec
from agent_sandbox_eval.trajectories.recorder import TrajectoryRecorder


def _spec(tmp_path: Path) -> ExperimentSpec:
    data = {
        "schema_version": 1,
        "name": "deterministic-fixtures",
        "seed": 23,
        "trials": 2,
        "concurrency": 3,
        "benchmark": {"name": "terminal", "split": "all"},
        "budgets": {
            "timeout_seconds": 30,
            "max_tool_calls": 5,
            "max_input_tokens": None,
            "max_output_tokens": None,
            "max_estimated_cost_usd": None,
        },
        "retry": {"max_attempts": 2, "on": ["environment_setup_failure", "runner_error"]},
        "environment": {"id": "fixture", "docker_image": "fixture:latest", "metadata": {}},
        "artifacts": {"root": str(tmp_path / "matrix"), "normalize_timestamps": True},
        "matrix": [
            {
                "id": "oracle",
                "agent": {"name": "scripted", "metadata": {"control": "oracle"}},
                "model": {"provider": "local-solution", "name": "local-solution", "metadata": {}},
            },
            {
                "id": "local-solution",
                "agent": {"name": "react", "metadata": {"control": "harness"}},
                "model": {"provider": "local-solution", "name": "local-solution", "metadata": {}},
            },
            {
                "id": "noop",
                "agent": {"name": "noop", "metadata": {"control": "negative"}},
                "model": {"provider": "local-solution", "name": "local-solution", "metadata": {}},
            },
        ],
    }
    return ExperimentSpec.from_dict(data, tmp_path / "experiment.yaml")


def _tasks() -> list:
    base = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    return [
        replace(base, id=task_id, title=task_id)
        for task_id in ["normal", "partial", "retry", "timeout", "setup-failure"]
    ]


class _FixtureExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int, int]] = []

    def __call__(self, context: AttemptContext) -> AttemptObservation:
        key = (context.cell.id, context.task.id, context.trial, context.attempt)
        self.calls.append(key)
        passed = context.cell.id == "oracle"
        failure_mode = None if passed else "no_progress"
        failure_scope = "passed" if passed else "capability"
        if context.cell.id == "local-solution":
            passed = True
            failure_mode = None
            failure_scope = "passed"
            if context.task.id == "partial" and context.trial == 2:
                passed = False
                failure_mode = "incomplete_verification"
                failure_scope = "capability"
            elif context.task.id == "retry" and context.attempt == 1:
                passed = False
                failure_mode = "environment_setup_failure"
                failure_scope = "environment"
            elif context.task.id == "timeout":
                passed = False
                failure_mode = "timeout"
                failure_scope = "budget"
            elif context.task.id == "setup-failure":
                passed = False
                failure_mode = "environment_setup_failure"
                failure_scope = "environment"
        self._write_raw(context, passed, failure_mode)
        return AttemptObservation(
            passed=passed,
            failure_mode=failure_mode,
            failure_scope=failure_scope,
            duration_ms=10,
            input_tokens=100 if context.cell.id == "local-solution" else 0,
            output_tokens=20 if context.cell.id == "local-solution" else 0,
        )

    @staticmethod
    def _write_raw(context: AttemptContext, passed: bool, failure_mode: str | None) -> None:
        recorder = TrajectoryRecorder(context.trajectory_path, context.run_id, normalize_timestamps=True)
        recorder.record("run_start", agent=context.cell.agent.name, task_count=1)
        recorder.record("task_start", context.task.id, agent=context.cell.agent.name)
        if context.cell.id == "local-solution":
            recorder.record(
                "model_call",
                context.task.id,
                provider="local-solution",
                model="local-solution",
                input_tokens=100,
                output_tokens=20,
            )
        recorder.record(
            "grader_result",
            context.task.id,
            passed=passed,
            score=1.0 if passed else 0.0,
            failure_mode=failure_mode,
            evidence=[],
            raw_result={"duration_ms": 1},
        )
        recorder.record(
            "run_end",
            agent=context.cell.agent.name,
            passed_tasks=1 if passed else 0,
            total_tasks=1,
        )


def test_pass_at_k_and_pass_power_k_have_distinct_meanings() -> None:
    assert empirical_pass_at_k(n=3, c=2, k=2) == 1.0
    assert empirical_pass_power_k(n=3, c=2, k=2) == pytest.approx(1 / 3)


def test_deterministic_matrix_fixtures_and_resume_are_byte_stable(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    tasks = _tasks()
    executor = _FixtureExecutor()

    first = run_matrix(spec, tasks, attempt_executor=executor)
    first_summary = first.summary_path.read_bytes()
    first_report = first.report_path.read_bytes()
    first_call_count = len(executor.calls)
    second = run_matrix(spec, tasks, attempt_executor=executor)

    assert first.scheduled_units == 30
    assert first.executed_attempts > first.scheduled_units
    assert second.resumed_units == second.scheduled_units
    assert second.executed_attempts == 0
    assert len(executor.calls) == first_call_count
    assert second.summary_path.read_bytes() == first_summary
    assert second.report_path.read_bytes() == first_report
    cells = {cell["id"]: cell for cell in second.summary["cells"]}
    assert cells["oracle"]["pass_at_1"] == 1.0
    assert cells["noop"]["pass_at_1"] == 0.0
    assert cells["local-solution"]["retry_accounting"]["retry_assisted_passes"] == 2
    assert cells["local-solution"]["environment_invalid_trials"] == 4
    assert cells["local-solution"]["failure_scopes"]["budget"] == 2
    assert cells["local-solution"]["estimated_cost_usd"] is None


def test_report_regeneration_fails_closed_on_corrupted_raw_event(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    tasks = _tasks()[:1]
    run_matrix(spec, tasks, attempt_executor=_FixtureExecutor())
    marker_path = next(spec.artifacts.root.glob("raw/**/*.attempt.json"))
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    raw_path = spec.artifacts.root / marker["raw_path"]
    lines = raw_path.read_text(encoding="utf-8").splitlines()
    raw_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="hash mismatch"):
        regenerate_matrix_reports(spec, tasks)


def test_cost_is_estimated_only_with_explicit_pricing_source(tmp_path: Path) -> None:
    base = _spec(tmp_path)
    local_cell = next(cell for cell in base.matrix if cell.id == "local-solution")
    priced_cell = replace(
        local_cell,
        model=replace(
            local_cell.model,
            pricing=PricingSpec(
                source="provider-pricing-2026-07-14",
                input_per_million_usd=2.0,
                output_per_million_usd=8.0,
            ),
        ),
    )
    spec = replace(
        base,
        matrix=[priced_cell],
        artifacts=replace(base.artifacts, root=tmp_path / "priced-matrix"),
    )

    result = run_matrix(spec, _tasks()[:1], attempt_executor=_FixtureExecutor())
    cell = result.summary["cells"][0]

    assert cell["estimated_cost_usd"] == pytest.approx(0.00072)
    assert cell["pricing_source"] == "provider-pricing-2026-07-14"
