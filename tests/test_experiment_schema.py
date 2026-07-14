from pathlib import Path

import pytest
import yaml

from agent_sandbox_eval.experiments.schema import ExperimentSpec, load_experiment


def _config(tmp_path: Path) -> dict:
    return {
        "schema_version": 1,
        "name": "schema-test",
        "seed": 17,
        "trials": 3,
        "concurrency": 2,
        "benchmark": {"name": "all", "split": "smoke"},
        "budgets": {
            "timeout_seconds": 30,
            "max_tool_calls": 5,
            "max_input_tokens": 1000,
            "max_output_tokens": 500,
        },
        "retry": {"max_attempts": 2, "on": ["environment_setup_failure", "runner_error"]},
        "environment": {
            "id": "docker-local",
            "docker_image": "python:3.13-slim",
            "metadata": {"network": "none"},
        },
        "artifacts": {
            "root": str(tmp_path / "artifacts"),
            "raw_dir": "raw-events",
            "summary_json": "reports/summary.json",
            "report_markdown": "reports/summary.md",
            "normalize_timestamps": True,
        },
        "matrix": [
            {
                "id": "react-local",
                "agent": {"name": "react", "metadata": {"loop": "react"}},
                "model": {
                    "provider": "local-solution",
                    "name": "local-solution",
                    "metadata": {"control": True},
                    "pricing": None,
                },
            }
        ],
    }


def test_loads_versioned_experiment_and_has_stable_fingerprint(tmp_path: Path) -> None:
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(_config(tmp_path), sort_keys=False), encoding="utf-8")

    first = load_experiment(path)
    second = load_experiment(path)

    assert first.fingerprint == second.fingerprint
    assert first.trials == 3
    assert first.matrix[0].model.pricing is None
    assert first.artifacts.summary_json == "reports/summary.json"


def test_cost_budget_requires_explicit_pricing(tmp_path: Path) -> None:
    data = _config(tmp_path)
    data["budgets"]["max_estimated_cost_usd"] = 1.0

    with pytest.raises(ValueError, match="requires explicit pricing"):
        ExperimentSpec.from_dict(data, tmp_path / "experiment.yaml")
