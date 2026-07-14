from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from agent_sandbox_eval.experiments.artifacts import write_atomic_json


def write_experiment_reports(
    summary: dict[str, object],
    json_path: Path,
    markdown_path: Path,
) -> tuple[Path, Path]:
    write_atomic_json(json_path, summary)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(build_experiment_markdown(summary), encoding="utf-8")
    return json_path, markdown_path


def build_experiment_markdown(summary: dict[str, object]) -> str:
    experiment = summary["experiment"]
    assert isinstance(experiment, dict)
    cells = summary["cells"]
    assert isinstance(cells, list)
    artifact_counts = summary["artifact_counts"]
    assert isinstance(artifact_counts, dict)
    lines = [
        "# Agent Sandbox Eval Experiment Report",
        "",
        f"Experiment: `{experiment['name']}`.",
        f"Configuration fingerprint: `{experiment['fingerprint']}`.",
        f"Benchmark split: `{experiment['benchmark']['split']}`.",
        f"Trials per task: {experiment['trials']}.",
        f"Recorded attempts: {artifact_counts['attempts']}.",
        "",
        "Capability metrics use first attempts and exclude trials invalidated by environment, task, harness, or configuration failures.",
        "Observed first-attempt pass rate keeps environment-invalid trials in the denominator.",
        "Retry-assisted passes are reported separately and never increase pass@k or pass^k.",
        "",
        "## Matrix Summary",
        "",
        "| Cell | Agent | Provider | Eligible | Invalid | Env invalid | Observed pass | pass@1 | Retry-assisted | Cost |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for raw_cell in cells:
        cell: dict[str, Any] = raw_cell
        pass_at_1 = _format_rate(cell["pass_at_1"])
        observed = _format_rate(cell["observed_first_attempt_pass_rate"])
        cost = "unavailable"
        if cell["estimated_cost_usd"] is not None:
            cost = f"${float(cell['estimated_cost_usd']):.6f}"
        lines.append(
            "| {id} | {agent} | {provider} | {eligible} | {all_invalid} | {invalid} | {observed} | {pass_at_1} | {retry} | {cost} |".format(
                id=cell["id"],
                agent=cell["agent"]["name"],
                provider=cell["model"]["provider"],
                eligible=cell["capability_eligible_trials"],
                all_invalid=cell["non_capability_invalid_trials"],
                invalid=cell["environment_invalid_trials"],
                observed=observed,
                pass_at_1=pass_at_1,
                retry=cell["retry_accounting"]["retry_assisted_passes"],
                cost=cost,
            )
        )
    for raw_cell in cells:
        cell = raw_cell
        assert isinstance(cell, dict)
        lines.extend(
            [
                "",
                f"## `{cell['id']}`",
                "",
                "### Reliability",
                "",
                "| k | pass@k | pass^k |",
                "| ---: | ---: | ---: |",
            ]
        )
        pass_at_k = cell["pass_at_k"]
        pass_power_k = cell["pass_power_k"]
        assert isinstance(pass_at_k, dict)
        assert isinstance(pass_power_k, dict)
        for k in sorted(pass_at_k, key=int):
            lines.append(
                f"| {k} | {_format_rate(pass_at_k[k])} | {_format_rate(pass_power_k[k])} |"
            )
        lines.extend(["", "### Failure Distribution", ""])
        failure_scopes = cell["failure_scopes"]
        failure_modes = cell["failure_modes"]
        assert isinstance(failure_scopes, dict)
        assert isinstance(failure_modes, dict)
        if not failure_scopes:
            lines.append("No first-attempt failures were recorded.")
        else:
            for name, count in failure_scopes.items():
                lines.append(f"- Failure scope `{name}`: {count}.")
            for name, count in failure_modes.items():
                lines.append(f"- Failure mode `{name}`: {count}.")
        pricing_source = cell.get("pricing_source")
        lines.extend(["", "### Usage", ""])
        tokens = cell["tokens"]
        latency = cell["latency_ms"]
        retry = cell["retry_accounting"]
        assert isinstance(tokens, dict)
        assert isinstance(latency, dict)
        assert isinstance(retry, dict)
        lines.append(
            f"First attempts used {tokens['first_attempt_input']} input tokens and {tokens['first_attempt_output']} output tokens."
        )
        lines.append(
            f"All attempts used {tokens['all_attempt_input']} input tokens and {tokens['all_attempt_output']} output tokens."
        )
        lines.append(f"Mean capability-eligible latency was {_format_ms(latency['mean'])}.")
        lines.append(
            f"Retries: {retry['retry_attempts']} attempts, {retry['retry_assisted_passes']} assisted passes."
        )
        if pricing_source:
            lines.append(f"Estimated cost uses the explicitly recorded pricing source `{pricing_source}`.")
        else:
            lines.append("Estimated cost is unavailable because no pricing source was supplied.")
    return "\n".join(lines).rstrip() + "\n"


def _format_rate(value: object) -> str:
    if value is None:
        return "unavailable"
    return f"{float(cast(float | int | str, value)):.1%}"


def _format_ms(value: object) -> str:
    if value is None:
        return "unavailable"
    return f"{float(cast(float | int | str, value)):.0f}ms"
