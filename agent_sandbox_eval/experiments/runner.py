from __future__ import annotations

import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from agent_sandbox_eval.agents.registry import get_agent
from agent_sandbox_eval.benchmarks.schema import Limits, Task
from agent_sandbox_eval.experiments.artifacts import (
    ArtifactValidationError,
    ensure_config_snapshot,
    read_attempt_marker,
    sha256_file,
    validate_trajectory,
    write_atomic_json,
)
from agent_sandbox_eval.experiments.metrics import build_experiment_summary
from agent_sandbox_eval.experiments.reports import write_experiment_reports
from agent_sandbox_eval.experiments.schema import ExperimentSpec, MatrixCell
from agent_sandbox_eval.runner import Runner


@dataclass(frozen=True)
class AttemptContext:
    spec: ExperimentSpec
    cell: MatrixCell
    task: Task
    trial: int
    attempt: int
    seed: int
    run_id: str
    trajectory_path: Path


@dataclass(frozen=True)
class AttemptObservation:
    passed: bool | None
    failure_mode: str | None
    failure_scope: str
    duration_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


AttemptExecutor = Callable[[AttemptContext], AttemptObservation]


@dataclass(frozen=True)
class MatrixRunResult:
    scheduled_units: int
    resumed_units: int
    executed_attempts: int
    summary_path: Path
    report_path: Path
    summary: dict[str, object]


@dataclass(frozen=True)
class _Unit:
    cell: MatrixCell
    task: Task
    trial: int
    seed: int


def run_matrix(
    spec: ExperimentSpec,
    tasks: list[Task],
    attempt_executor: AttemptExecutor | None = None,
) -> MatrixRunResult:
    if not tasks:
        raise ValueError("matrix requires at least one task")
    root = spec.artifacts.root
    ensure_config_snapshot(root, spec.to_dict())
    executor = attempt_executor or execute_attempt
    units = [
        _Unit(cell=cell, task=task, trial=trial, seed=_trial_seed(spec, cell, task, trial))
        for cell in spec.matrix
        for task in sorted(tasks, key=lambda item: (item.benchmark, item.id))
        for trial in range(1, spec.trials + 1)
    ]
    pending: list[tuple[_Unit, int]] = []
    resumed = 0
    for unit in units:
        next_attempt = _next_attempt(spec, unit)
        if next_attempt is None:
            resumed += 1
        else:
            pending.append((unit, next_attempt))

    executed_attempts = 0
    if pending:
        with ThreadPoolExecutor(max_workers=spec.concurrency, thread_name_prefix="ase-matrix") as pool:
            futures = {
                pool.submit(_run_unit, spec, unit, start_attempt, executor): unit
                for unit, start_attempt in pending
            }
            for future in as_completed(futures):
                executed_attempts += future.result()

    attempts = collect_attempts(spec, units, require_terminal=True)
    summary = build_experiment_summary(spec, attempts, [task.id for task in tasks])
    summary_path = root / spec.artifacts.summary_json
    report_path = root / spec.artifacts.report_markdown
    write_experiment_reports(summary, summary_path, report_path)
    return MatrixRunResult(
        scheduled_units=len(units),
        resumed_units=resumed,
        executed_attempts=executed_attempts,
        summary_path=summary_path,
        report_path=report_path,
        summary=summary,
    )


def regenerate_matrix_reports(spec: ExperimentSpec, tasks: list[Task]) -> MatrixRunResult:
    units = [
        _Unit(cell=cell, task=task, trial=trial, seed=_trial_seed(spec, cell, task, trial))
        for cell in spec.matrix
        for task in sorted(tasks, key=lambda item: (item.benchmark, item.id))
        for trial in range(1, spec.trials + 1)
    ]
    ensure_config_snapshot(spec.artifacts.root, spec.to_dict())
    attempts = collect_attempts(spec, units, require_terminal=True)
    summary = build_experiment_summary(spec, attempts, [task.id for task in tasks])
    summary_path = spec.artifacts.root / spec.artifacts.summary_json
    report_path = spec.artifacts.root / spec.artifacts.report_markdown
    write_experiment_reports(summary, summary_path, report_path)
    return MatrixRunResult(
        scheduled_units=len(units),
        resumed_units=len(units),
        executed_attempts=0,
        summary_path=summary_path,
        report_path=report_path,
        summary=summary,
    )


def execute_attempt(context: AttemptContext) -> AttemptObservation:
    task = _apply_budgets(context.task, context.spec)
    started = time.monotonic()
    try:
        agent = get_agent(
            context.cell.agent.name,
            provider_name=context.cell.model.provider,
            model=context.cell.model.name,
        )
        Runner(
            agent=agent,
            output_path=context.trajectory_path,
            docker_image=context.spec.environment.docker_image,
            run_id=context.run_id,
            normalize_timestamps=context.spec.artifacts.normalize_timestamps,
            run_metadata={
                "experiment": context.spec.name,
                "experiment_fingerprint": context.spec.fingerprint,
                "matrix_cell": context.cell.id,
                "provider": context.cell.model.provider,
                "model": context.cell.model.name,
                "trial": context.trial,
                "attempt": context.attempt,
                "seed": context.seed,
                "environment_id": context.spec.environment.id,
            },
        ).run([task])
    except Exception as exc:
        duration_ms = round((time.monotonic() - started) * 1000)
        exception_mode, exception_scope = _classify_execution_exception(exc)
        return AttemptObservation(
            passed=None,
            failure_mode=exception_mode,
            failure_scope=exception_scope,
            duration_ms=duration_ms,
            error=f"{type(exc).__name__}: {str(exc)[:1000]}",
        )

    duration_ms = round((time.monotonic() - started) * 1000)
    events = validate_trajectory(
        context.trajectory_path,
        expected_run_id=context.run_id,
        expected_task_id=task.id,
        require_complete=True,
    )
    grade = next(event for event in events if event.get("event_type") == "grader_result")
    model_calls = [event for event in events if event.get("event_type") == "model_call"]
    input_tokens = sum(int(event.get("input_tokens") or 0) for event in model_calls)
    output_tokens = sum(int(event.get("output_tokens") or 0) for event in model_calls)
    passed = bool(grade.get("passed"))
    failure_mode = None if passed else str(grade.get("failure_mode") or "unknown_failure")
    failure_scope = "passed" if passed else _failure_scope(failure_mode)
    budget_failure = _budget_failure(context, input_tokens, output_tokens)
    if budget_failure:
        passed = False
        failure_mode = budget_failure
        failure_scope = "budget"
    return AttemptObservation(
        passed=passed,
        failure_mode=failure_mode,
        failure_scope=failure_scope,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def collect_attempts(
    spec: ExperimentSpec,
    units: list[_Unit],
    require_terminal: bool,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for unit in units:
        terminal = False
        for attempt in range(1, spec.retry.max_attempts + 1):
            trajectory_path, marker_path = _artifact_paths(spec, unit, attempt)
            if not marker_path.exists():
                if trajectory_path.exists():
                    raise ArtifactValidationError(
                        f"orphan raw trajectory has no attempt marker: {trajectory_path}"
                    )
                break
            marker = read_attempt_marker(marker_path, spec.artifacts.root)
            _validate_marker_identity(spec, unit, attempt, marker)
            collected.append(marker)
            terminal = _is_terminal(marker, attempt, spec.retry.max_attempts)
            if terminal:
                _reject_later_attempts(spec, unit, attempt)
                break
        if require_terminal and not terminal:
            raise ArtifactValidationError(
                f"matrix unit has no terminal attempt: cell={unit.cell.id} task={unit.task.id} trial={unit.trial}"
            )
    return sorted(
        collected,
        key=lambda item: (str(item["cell_id"]), str(item["task_id"]), int(item["trial"]), int(item["attempt"])),
    )


def _run_unit(
    spec: ExperimentSpec,
    unit: _Unit,
    start_attempt: int,
    executor: AttemptExecutor,
) -> int:
    executed = 0
    for attempt in range(start_attempt, spec.retry.max_attempts + 1):
        trajectory_path, marker_path = _artifact_paths(spec, unit, attempt)
        trajectory_path.parent.mkdir(parents=True, exist_ok=True)
        if trajectory_path.exists() or marker_path.exists():
            raise ArtifactValidationError(
                f"refusing to overwrite an existing attempt artifact: {trajectory_path}"
            )
        run_id = _run_id(spec, unit, attempt)
        context = AttemptContext(
            spec=spec,
            cell=unit.cell,
            task=unit.task,
            trial=unit.trial,
            attempt=attempt,
            seed=unit.seed,
            run_id=run_id,
            trajectory_path=trajectory_path,
        )
        observation = executor(context)
        executed += 1
        marker = _write_attempt(spec, context, observation, marker_path)
        if _is_terminal(marker, attempt, spec.retry.max_attempts):
            break
    return executed


def _write_attempt(
    spec: ExperimentSpec,
    context: AttemptContext,
    observation: AttemptObservation,
    marker_path: Path,
) -> dict[str, object]:
    status = "passed" if observation.passed is True else "failed"
    if observation.error is not None:
        status = "runner_error"
    elif observation.failure_scope == "environment":
        status = "environment_failed"
    raw_path: str | None = None
    raw_hash: str | None = None
    if context.trajectory_path.exists():
        validate_trajectory(
            context.trajectory_path,
            expected_run_id=context.run_id,
            expected_task_id=context.task.id,
            require_complete=status != "runner_error",
        )
        raw_path = str(context.trajectory_path.relative_to(spec.artifacts.root))
        raw_hash = sha256_file(context.trajectory_path)
    elif status != "runner_error":
        raise ArtifactValidationError(
            f"attempt executor did not produce a raw trajectory: {context.trajectory_path}"
        )
    retry_eligible = observation.failure_mode in set(spec.retry.on)
    estimated_cost = _estimated_cost(context.cell, observation.input_tokens, observation.output_tokens)
    marker: dict[str, object] = {
        "run_id": context.run_id,
        "cell_id": context.cell.id,
        "task_id": context.task.id,
        "trial": context.trial,
        "attempt": context.attempt,
        "seed": context.seed,
        "status": status,
        "passed": observation.passed,
        "failure_mode": observation.failure_mode,
        "failure_scope": observation.failure_scope,
        "retry_eligible": retry_eligible,
        "duration_ms": observation.duration_ms,
        "input_tokens": observation.input_tokens,
        "output_tokens": observation.output_tokens,
        "estimated_cost_usd": estimated_cost,
        "pricing_source": context.cell.model.pricing.source if context.cell.model.pricing else None,
        "raw_path": raw_path,
        "raw_sha256": raw_hash,
        "error": observation.error,
    }
    write_atomic_json(marker_path, marker)
    return marker


def _next_attempt(spec: ExperimentSpec, unit: _Unit) -> int | None:
    for attempt in range(1, spec.retry.max_attempts + 1):
        trajectory_path, marker_path = _artifact_paths(spec, unit, attempt)
        if not marker_path.exists():
            if trajectory_path.exists():
                raise ArtifactValidationError(
                    f"orphan raw trajectory has no attempt marker: {trajectory_path}"
                )
            return attempt
        marker = read_attempt_marker(marker_path, spec.artifacts.root)
        _validate_marker_identity(spec, unit, attempt, marker)
        if _is_terminal(marker, attempt, spec.retry.max_attempts):
            _reject_later_attempts(spec, unit, attempt)
            return None
    return None


def _is_terminal(marker: dict[str, Any] | dict[str, object], attempt: int, max_attempts: int) -> bool:
    return bool(marker.get("passed") is True or not marker.get("retry_eligible") or attempt >= max_attempts)


def _reject_later_attempts(spec: ExperimentSpec, unit: _Unit, terminal_attempt: int) -> None:
    for attempt in range(terminal_attempt + 1, spec.retry.max_attempts + 1):
        trajectory_path, marker_path = _artifact_paths(spec, unit, attempt)
        if trajectory_path.exists() or marker_path.exists():
            raise ArtifactValidationError(
                "attempt artifacts exist after a terminal attempt: "
                f"cell={unit.cell.id} task={unit.task.id} trial={unit.trial} attempt={attempt}"
            )


def _validate_marker_identity(
    spec: ExperimentSpec,
    unit: _Unit,
    attempt: int,
    marker: dict[str, Any],
) -> None:
    expected = {
        "run_id": _run_id(spec, unit, attempt),
        "cell_id": unit.cell.id,
        "task_id": unit.task.id,
        "trial": unit.trial,
        "attempt": attempt,
        "seed": unit.seed,
    }
    mismatches = [key for key, value in expected.items() if marker.get(key) != value]
    if mismatches:
        raise ArtifactValidationError(
            "attempt marker identity mismatch for fields " + ", ".join(mismatches)
        )


def _artifact_paths(spec: ExperimentSpec, unit: _Unit, attempt: int) -> tuple[Path, Path]:
    directory = (
        spec.artifacts.root
        / spec.artifacts.raw_dir
        / _slug(unit.cell.id)
        / _slug(unit.task.id)
        / f"trial-{unit.trial:04d}"
    )
    trajectory = directory / f"attempt-{attempt:02d}.jsonl"
    marker = directory / f"attempt-{attempt:02d}.attempt.json"
    return trajectory, marker


def _run_id(spec: ExperimentSpec, unit: _Unit, attempt: int) -> str:
    return (
        f"ase-{spec.fingerprint}-{_slug(unit.cell.id)}-{_slug(unit.task.id)}-"
        f"t{unit.trial:04d}-s{unit.seed:010d}-a{attempt:02d}"
    )


def _trial_seed(spec: ExperimentSpec, cell: MatrixCell, task: Task, trial: int) -> int:
    payload = f"{spec.seed}:{cell.id}:{task.id}:{trial}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") & 0x7FFFFFFF


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    if not cleaned:
        raise ValueError(f"identifier cannot be converted to an artifact path: {value!r}")
    return cleaned


def _apply_budgets(task: Task, spec: ExperimentSpec) -> Task:
    limits: Limits = task.limits
    timeout = limits.timeout_seconds
    max_tool_calls = limits.max_tool_calls
    if spec.budgets.timeout_seconds is not None:
        timeout = min(timeout, spec.budgets.timeout_seconds)
    if spec.budgets.max_tool_calls is not None:
        max_tool_calls = min(max_tool_calls, spec.budgets.max_tool_calls)
    return replace(task, limits=replace(limits, timeout_seconds=timeout, max_tool_calls=max_tool_calls))


def _failure_scope(failure_mode: str | None) -> str:
    if failure_mode == "environment_setup_failure":
        return "environment"
    if failure_mode == "runner_error":
        return "harness"
    if failure_mode in {"timeout", "exceeded_budget", "exceeded_experiment_budget"}:
        return "budget"
    if failure_mode == "grader_or_task_bug":
        return "task"
    return "capability"


def _classify_execution_exception(exc: Exception) -> tuple[str, str]:
    message = str(exc).lower()
    if isinstance(exc, ValueError):
        if "unknown agent" in message or "unknown provider" in message or "unavailable tool" in message:
            return "configuration_error", "configuration"
        return "invalid_provider_output", "capability"
    if isinstance(exc, RuntimeError):
        if "api_key is required" in message:
            return "configuration_error", "configuration"
        if "api request failed" in message:
            return "provider_transport_failure", "environment"
    return "runner_error", "harness"


def _budget_failure(context: AttemptContext, input_tokens: int, output_tokens: int) -> str | None:
    budgets = context.spec.budgets
    if budgets.max_input_tokens is not None and input_tokens > budgets.max_input_tokens:
        return "exceeded_experiment_budget"
    if budgets.max_output_tokens is not None and output_tokens > budgets.max_output_tokens:
        return "exceeded_experiment_budget"
    estimated_cost = _estimated_cost(context.cell, input_tokens, output_tokens)
    if (
        budgets.max_estimated_cost_usd is not None
        and estimated_cost is not None
        and estimated_cost > budgets.max_estimated_cost_usd
    ):
        return "exceeded_experiment_budget"
    return None


def _estimated_cost(cell: MatrixCell, input_tokens: int, output_tokens: int) -> float | None:
    if cell.model.pricing is None:
        return None
    return round(
        (
            input_tokens * cell.model.pricing.input_per_million_usd
            + output_tokens * cell.model.pricing.output_per_million_usd
        )
        / 1_000_000,
        8,
    )
