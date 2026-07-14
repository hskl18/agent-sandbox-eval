from __future__ import annotations

import math
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from agent_sandbox_eval.experiments.schema import ExperimentSpec, MatrixCell
from agent_sandbox_eval.version import EXPERIMENT_REPORT_SCHEMA_VERSION


CAPABILITY_ELIGIBLE_SCOPES = {"passed", "capability", "budget"}


def build_experiment_summary(
    spec: ExperimentSpec,
    attempts: list[dict[str, Any]],
    task_ids: list[str],
) -> dict[str, object]:
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        by_cell[str(attempt["cell_id"])].append(attempt)
    return {
        "schema_version": EXPERIMENT_REPORT_SCHEMA_VERSION,
        "experiment": {
            "name": spec.name,
            "fingerprint": spec.fingerprint,
            "seed": spec.seed,
            "trials": spec.trials,
            "benchmark": spec.benchmark.to_dict(),
            "environment": spec.environment.to_dict(),
            "budgets": spec.budgets.to_dict(),
            "retry": spec.retry.to_dict(),
        },
        "task_ids": sorted(task_ids),
        "cells": [
            _summarize_cell(cell, by_cell.get(cell.id, []), sorted(task_ids), spec.trials)
            for cell in spec.matrix
        ],
        "artifact_counts": {
            "attempts": len(attempts),
            "raw_trajectories": sum(1 for attempt in attempts if attempt.get("raw_path")),
        },
    }


def empirical_pass_at_k(n: int, c: int, k: int) -> float | None:
    if k <= 0:
        raise ValueError("k must be positive")
    if n < k:
        return None
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def empirical_pass_power_k(n: int, c: int, k: int) -> float | None:
    if k <= 0:
        raise ValueError("k must be positive")
    if n < k:
        return None
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)


def _summarize_cell(
    cell: MatrixCell,
    attempts: list[dict[str, Any]],
    task_ids: list[str],
    trials: int,
) -> dict[str, object]:
    attempts = sorted(
        attempts,
        key=lambda item: (str(item["task_id"]), int(item["trial"]), int(item["attempt"])),
    )
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        grouped[(str(attempt["task_id"]), int(attempt["trial"]))].append(attempt)
    first_attempts = [items[0] for items in grouped.values()]
    eligible = [item for item in first_attempts if item.get("failure_scope") in CAPABILITY_ELIGIBLE_SCOPES]
    first_passes = sum(1 for item in first_attempts if item.get("passed") is True)
    scheduled = len(task_ids) * trials

    per_task: list[dict[str, Any]] = [
        _summarize_task(task_id, grouped, trials)
        for task_id in task_ids
    ]
    max_k = min(trials, 5)
    pass_at_k: dict[str, float | None] = {}
    pass_power_k: dict[str, float | None] = {}
    for k in range(1, max_k + 1):
        at_values = [
            float(task["pass_at_k"][str(k)])
            for task in per_task
            if task["pass_at_k"][str(k)] is not None
        ]
        power_values = [
            float(task["pass_power_k"][str(k)])
            for task in per_task
            if task["pass_power_k"][str(k)] is not None
        ]
        pass_at_k[str(k)] = mean(at_values) if at_values else None
        pass_power_k[str(k)] = mean(power_values) if power_values else None

    retry_assisted = 0
    eventual_passes = 0
    for unit_attempts in grouped.values():
        if any(item.get("passed") is True for item in unit_attempts):
            eventual_passes += 1
            if unit_attempts[0].get("passed") is not True:
                retry_assisted += 1

    failure_modes = Counter(
        str(item.get("failure_mode") or "unknown")
        for item in first_attempts
        if item.get("passed") is not True
    )
    failure_scopes = Counter(
        str(item.get("failure_scope") or "unknown")
        for item in first_attempts
        if item.get("passed") is not True
    )
    eligible_latencies = [int(item.get("duration_ms") or 0) for item in eligible]
    all_input_tokens = sum(int(item.get("input_tokens") or 0) for item in attempts)
    all_output_tokens = sum(int(item.get("output_tokens") or 0) for item in attempts)
    first_input_tokens = sum(int(item.get("input_tokens") or 0) for item in first_attempts)
    first_output_tokens = sum(int(item.get("output_tokens") or 0) for item in first_attempts)
    cost_values = [item.get("estimated_cost_usd") for item in attempts]
    estimated_cost: float | None = None
    if cell.model.pricing is not None:
        estimated_cost = sum(float(value or 0.0) for value in cost_values)

    return {
        "id": cell.id,
        "agent": cell.agent.to_dict(),
        "model": cell.model.to_dict(),
        "scheduled_trials": scheduled,
        "recorded_trials": len(grouped),
        "capability_eligible_trials": len(eligible),
        "environment_invalid_trials": sum(
            1 for item in first_attempts if item.get("failure_scope") == "environment"
        ),
        "non_capability_invalid_trials": sum(
            1 for item in first_attempts if item.get("failure_scope") not in CAPABILITY_ELIGIBLE_SCOPES
        ),
        "observed_first_attempt_pass_rate": first_passes / scheduled if scheduled else 0.0,
        "pass_at_1": pass_at_k.get("1"),
        "pass_at_k": pass_at_k,
        "pass_power_k": pass_power_k,
        "retry_accounting": {
            "total_attempts": len(attempts),
            "retry_attempts": max(0, len(attempts) - len(grouped)),
            "first_attempt_passes": first_passes,
            "retry_assisted_passes": retry_assisted,
            "eventual_passes": eventual_passes,
        },
        "latency_ms": {
            "mean": mean(eligible_latencies) if eligible_latencies else None,
            "p50": _percentile(eligible_latencies, 0.50),
            "p95": _percentile(eligible_latencies, 0.95),
        },
        "tokens": {
            "first_attempt_input": first_input_tokens,
            "first_attempt_output": first_output_tokens,
            "all_attempt_input": all_input_tokens,
            "all_attempt_output": all_output_tokens,
        },
        "estimated_cost_usd": estimated_cost,
        "pricing_source": cell.model.pricing.source if cell.model.pricing else None,
        "failure_modes": dict(sorted(failure_modes.items())),
        "failure_scopes": dict(sorted(failure_scopes.items())),
        "per_task": per_task,
    }


def _summarize_task(
    task_id: str,
    grouped: dict[tuple[str, int], list[dict[str, Any]]],
    trials: int,
) -> dict[str, Any]:
    first_attempts = [
        grouped[(task_id, trial)][0]
        for trial in range(1, trials + 1)
        if (task_id, trial) in grouped
    ]
    eligible = [item for item in first_attempts if item.get("failure_scope") in CAPABILITY_ELIGIBLE_SCOPES]
    successes = sum(1 for item in eligible if item.get("passed") is True)
    n = len(eligible)
    p = successes / n if n else None
    max_k = min(trials, 5)
    return {
        "task_id": task_id,
        "scheduled_trials": trials,
        "recorded_trials": len(first_attempts),
        "eligible_trials": n,
        "environment_invalid_trials": sum(
            1 for item in first_attempts if item.get("failure_scope") == "environment"
        ),
        "non_capability_invalid_trials": sum(
            1 for item in first_attempts if item.get("failure_scope") not in CAPABILITY_ELIGIBLE_SCOPES
        ),
        "successes": successes,
        "pass_at_1": p,
        "pass_at_k": {str(k): empirical_pass_at_k(n, successes, k) for k in range(1, max_k + 1)},
        "pass_power_k": {
            str(k): empirical_pass_power_k(n, successes, k) for k in range(1, max_k + 1)
        },
        "bernoulli_variance": p * (1.0 - p) if p is not None else None,
    }


def _percentile(values: list[int], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
