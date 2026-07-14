from __future__ import annotations

from typing import Any


CONTROL_EXPECTATIONS = {
    "scripted-oracle": {"pass_rate": 1.0, "failure_modes": {}, "failure_scopes": {}},
    "react-local-solution": {"pass_rate": 1.0, "failure_modes": {}, "failure_scopes": {}},
    "noop-negative-control": {
        "pass_rate": 0.0,
        "failure_mode": "no_progress",
        "failure_scope": "capability",
    },
}


def validate_local_control_summary(
    summary: dict[str, Any],
    *,
    expected_task_count: int,
    expected_trials: int,
) -> None:
    if expected_task_count <= 0 or expected_trials <= 0:
        raise ValueError("expected task and trial counts must be positive")
    task_ids = summary.get("task_ids")
    if (
        not isinstance(task_ids, list)
        or len(task_ids) != expected_task_count
        or len(set(task_ids)) != expected_task_count
        or any(not isinstance(task_id, str) or not task_id for task_id in task_ids)
    ):
        raise ValueError(f"matrix must contain exactly {expected_task_count} unique task ids")
    experiment = _mapping(summary.get("experiment"), "experiment")
    _expect(experiment.get("trials"), expected_trials, "experiment.trials")

    raw_cells = summary.get("cells")
    if not isinstance(raw_cells, list) or any(not isinstance(cell, dict) for cell in raw_cells):
        raise ValueError("matrix cells must be a list of objects")
    cells = {str(cell.get("id")): cell for cell in raw_cells}
    if set(cells) != set(CONTROL_EXPECTATIONS) or len(raw_cells) != len(cells):
        raise ValueError("matrix must contain exactly the three local control cells")

    scheduled = expected_task_count * expected_trials
    for cell_id, expectation in CONTROL_EXPECTATIONS.items():
        cell = cells[cell_id]
        pass_rate_value = expectation["pass_rate"]
        if isinstance(pass_rate_value, bool) or not isinstance(pass_rate_value, (int, float)):
            raise ValueError(f"invalid built-in pass-rate expectation for {cell_id}")
        pass_rate = float(pass_rate_value)
        passes = scheduled if pass_rate == 1.0 else 0
        for field in ["scheduled_trials", "recorded_trials", "capability_eligible_trials"]:
            _expect(cell.get(field), scheduled, f"{cell_id}.{field}")
        for field in ["environment_invalid_trials", "non_capability_invalid_trials"]:
            _expect(cell.get(field), 0, f"{cell_id}.{field}")
        _expect(cell.get("observed_first_attempt_pass_rate"), pass_rate, f"{cell_id}.pass_rate")
        _expect(cell.get("pass_at_1"), pass_rate, f"{cell_id}.pass_at_1")
        expected_k = {str(k): pass_rate for k in range(1, min(expected_trials, 5) + 1)}
        _expect(cell.get("pass_at_k"), expected_k, f"{cell_id}.pass_at_k")
        _expect(cell.get("pass_power_k"), expected_k, f"{cell_id}.pass_power_k")

        retry = _mapping(cell.get("retry_accounting"), f"{cell_id}.retry_accounting")
        expected_retry = {
            "total_attempts": scheduled,
            "retry_attempts": 0,
            "first_attempt_passes": passes,
            "retry_assisted_passes": 0,
            "eventual_passes": passes,
        }
        _expect(retry, expected_retry, f"{cell_id}.retry_accounting")
        tokens = _mapping(cell.get("tokens"), f"{cell_id}.tokens")
        _expect(
            tokens,
            {
                "first_attempt_input": 0,
                "first_attempt_output": 0,
                "all_attempt_input": 0,
                "all_attempt_output": 0,
            },
            f"{cell_id}.tokens",
        )
        _expect(cell.get("estimated_cost_usd"), None, f"{cell_id}.estimated_cost_usd")
        _expect(cell.get("pricing_source"), None, f"{cell_id}.pricing_source")

        if cell_id == "noop-negative-control":
            expected_failures = {str(expectation["failure_mode"]): scheduled}
            expected_scopes = {str(expectation["failure_scope"]): scheduled}
        else:
            expected_failures = {}
            expected_scopes = {}
        _expect(cell.get("failure_modes"), expected_failures, f"{cell_id}.failure_modes")
        _expect(cell.get("failure_scopes"), expected_scopes, f"{cell_id}.failure_scopes")
        _validate_per_task(cell_id, cell.get("per_task"), task_ids, expected_trials, pass_rate)

    counts = _mapping(summary.get("artifact_counts"), "artifact_counts")
    expected_attempts = scheduled * len(CONTROL_EXPECTATIONS)
    _expect(counts.get("attempts"), expected_attempts, "artifact_counts.attempts")
    _expect(
        counts.get("raw_trajectories"),
        expected_attempts,
        "artifact_counts.raw_trajectories",
    )


def _validate_per_task(
    cell_id: str,
    raw_tasks: object,
    task_ids: list[str],
    expected_trials: int,
    pass_rate: float,
) -> None:
    if not isinstance(raw_tasks, list) or any(not isinstance(task, dict) for task in raw_tasks):
        raise ValueError(f"{cell_id}.per_task must be a list of objects")
    tasks = {str(task.get("task_id")): task for task in raw_tasks}
    if set(tasks) != set(task_ids) or len(raw_tasks) != len(tasks):
        raise ValueError(f"{cell_id}.per_task does not match the selected task ids")
    successes = expected_trials if pass_rate == 1.0 else 0
    expected_k = {str(k): pass_rate for k in range(1, min(expected_trials, 5) + 1)}
    for task_id, task in tasks.items():
        prefix = f"{cell_id}.per_task.{task_id}"
        for field in ["scheduled_trials", "recorded_trials", "eligible_trials"]:
            _expect(task.get(field), expected_trials, f"{prefix}.{field}")
        for field in ["environment_invalid_trials", "non_capability_invalid_trials"]:
            _expect(task.get(field), 0, f"{prefix}.{field}")
        _expect(task.get("successes"), successes, f"{prefix}.successes")
        _expect(task.get("pass_at_1"), pass_rate, f"{prefix}.pass_at_1")
        _expect(task.get("pass_at_k"), expected_k, f"{prefix}.pass_at_k")
        _expect(task.get("pass_power_k"), expected_k, f"{prefix}.pass_power_k")
        _expect(task.get("bernoulli_variance"), 0.0, f"{prefix}.bernoulli_variance")


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _expect(actual: object, expected: object, field: str) -> None:
    if actual != expected:
        raise ValueError(f"{field} expected {expected!r}, got {actual!r}")
