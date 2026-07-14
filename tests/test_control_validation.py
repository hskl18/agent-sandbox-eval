from __future__ import annotations

from copy import deepcopy

import pytest

from agent_sandbox_eval.experiments.control_validation import validate_local_control_summary


def _matrix_summary() -> dict[str, object]:
    task_ids = ["mcp", "swe", "terminal"]
    cells = []
    for cell_id, passes in [
        ("scripted-oracle", 6),
        ("react-local-solution", 6),
        ("noop-negative-control", 0),
    ]:
        cell = {
            "id": cell_id,
            "scheduled_trials": 6,
            "recorded_trials": 6,
            "capability_eligible_trials": 6,
            "environment_invalid_trials": 0,
            "non_capability_invalid_trials": 0,
            "observed_first_attempt_pass_rate": passes / 6,
            "pass_at_1": passes / 6,
            "pass_at_k": {"1": passes / 6, "2": passes / 6},
            "pass_power_k": {"1": passes / 6, "2": passes / 6},
            "retry_accounting": {
                "total_attempts": 6,
                "retry_attempts": 0,
                "first_attempt_passes": passes,
                "retry_assisted_passes": 0,
                "eventual_passes": passes,
            },
            "tokens": {
                "first_attempt_input": 0,
                "first_attempt_output": 0,
                "all_attempt_input": 0,
                "all_attempt_output": 0,
            },
            "estimated_cost_usd": None,
            "pricing_source": None,
            "failure_modes": {} if passes else {"no_progress": 6},
            "failure_scopes": {} if passes else {"capability": 6},
            "per_task": [
                {
                    "task_id": task_id,
                    "scheduled_trials": 2,
                    "recorded_trials": 2,
                    "eligible_trials": 2,
                    "environment_invalid_trials": 0,
                    "non_capability_invalid_trials": 0,
                    "successes": 2 if passes else 0,
                    "pass_at_1": 1.0 if passes else 0.0,
                    "pass_at_k": {"1": 1.0 if passes else 0.0, "2": 1.0 if passes else 0.0},
                    "pass_power_k": {
                        "1": 1.0 if passes else 0.0,
                        "2": 1.0 if passes else 0.0,
                    },
                    "bernoulli_variance": 0.0,
                }
                for task_id in task_ids
            ],
        }
        cells.append(cell)
    return {
        "experiment": {"trials": 2},
        "task_ids": task_ids,
        "cells": cells,
        "artifact_counts": {"attempts": 18, "raw_trajectories": 18},
    }


def test_matrix_control_validation_accepts_expected_semantics() -> None:
    validate_local_control_summary(_matrix_summary(), expected_task_count=3, expected_trials=2)


def test_matrix_control_validation_rejects_false_noop_success() -> None:
    summary = deepcopy(_matrix_summary())
    noop = next(cell for cell in summary["cells"] if cell["id"] == "noop-negative-control")
    noop["observed_first_attempt_pass_rate"] = 1 / 6
    noop["pass_at_1"] = 1 / 6
    noop["retry_accounting"]["first_attempt_passes"] = 1
    noop["retry_accounting"]["eventual_passes"] = 1
    noop["failure_modes"] = {"no_progress": 5}
    noop["failure_scopes"] = {"capability": 5}

    with pytest.raises(ValueError, match="noop-negative-control"):
        validate_local_control_summary(summary, expected_task_count=3, expected_trials=2)
