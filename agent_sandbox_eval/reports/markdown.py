from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from agent_sandbox_eval.trajectories.replay import iter_events


def summarize_trajectory(trajectory_path: Path) -> dict[str, object]:
    events = iter_events(trajectory_path)
    task_start_events = [event for event in events if event.get("event_type") == "task_start"]
    grader_events = [event for event in events if event.get("event_type") == "grader_result"]
    tool_calls = [event for event in events if event.get("event_type") == "tool_call"]
    tool_results = [event for event in events if event.get("event_type") == "tool_result"]
    model_calls = [event for event in events if event.get("event_type") == "model_call"]
    run_end = next((event for event in reversed(events) if event.get("event_type") == "run_end"), {})
    total = len(grader_events)
    passed = sum(1 for event in grader_events if event.get("passed"))
    failures = Counter(event.get("failure_mode") or "passed" for event in grader_events)
    tool_use = Counter(str(event.get("tool") or "unknown") for event in tool_calls)
    average_score = (
        sum(float(event.get("score") or 0.0) for event in grader_events) / total
        if total
        else 0.0
    )
    timeout_count = sum(
        1
        for event in grader_events
        if event.get("failure_mode") in {"timeout", "exceeded_budget"}
        or (
            isinstance(event.get("raw_result"), dict)
            and (event.get("raw_result") or {}).get("exit_code") == 124
        )
    )
    task_or_grader_bug_count = sum(1 for event in grader_events if event.get("failure_mode") == "grader_or_task_bug")
    success_commands = {
        event.get("task_id"): event.get("success_command")
        for event in task_start_events
        if event.get("success_command")
    }
    verified_tasks = 0
    for task_id, command in success_commands.items():
        if any(
            event.get("task_id") == task_id
            and event.get("event_type") == "tool_call"
            and isinstance(event.get("input"), dict)
            and event.get("input", {}).get("cmd") == command
            for event in tool_calls
        ):
            verified_tasks += 1
    task_ids = {event.get("task_id") for event in grader_events}
    tool_calls_by_task = {
        task_id: sum(1 for event in tool_calls if event.get("task_id") == task_id)
        for task_id in task_ids
    }
    runtime_ms = sum(
        int(((event.get("output") or {}).get("duration_ms") or 0))
        for event in tool_results
        if isinstance(event.get("output"), dict)
    )
    runtime_ms += sum(
        int(((event.get("raw_result") or {}).get("duration_ms") or 0))
        for event in grader_events
        if isinstance(event.get("raw_result"), dict)
    )
    top_failure = ""
    for failure, _count in failures.most_common():
        if failure != "passed":
            top_failure = str(failure)
            break
    input_tokens = sum(int(event.get("input_tokens") or 0) for event in model_calls)
    output_tokens = sum(int(event.get("output_tokens") or 0) for event in model_calls)
    priced_model_calls = [event for event in model_calls if event.get("estimated_cost_usd") is not None]
    estimated_cost_usd = sum(float(event.get("estimated_cost_usd") or 0.0) for event in priced_model_calls)
    return {
        "path": str(trajectory_path),
        "agent": str(run_end.get("agent") or "unknown"),
        "total": total,
        "passed": passed,
        "pass_rate": passed / total if total else 0.0,
        "average_score": average_score,
        "tool_calls": len(tool_calls),
        "avg_tool_calls": (sum(tool_calls_by_task.values()) / total) if total else 0.0,
        "tool_use": tool_use,
        "runtime_ms": runtime_ms,
        "avg_runtime_ms": runtime_ms / total if total else 0.0,
        "timeout_rate": timeout_count / total if total else 0.0,
        "verification_rate": verified_tasks / total if total else 0.0,
        "task_or_grader_bug_count": task_or_grader_bug_count,
        "model_calls": len(model_calls),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "cost_coverage": len(priced_model_calls) / len(model_calls) if model_calls else 0.0,
        "failures": failures,
        "top_failure": top_failure,
        "grader_events": grader_events,
    }


def build_markdown_report(trajectory_path: Path) -> str:
    summary = summarize_trajectory(trajectory_path)
    failures = summary["failures"]
    assert isinstance(failures, Counter)
    tool_use = summary["tool_use"]
    assert isinstance(tool_use, Counter)
    grader_events = summary["grader_events"]
    assert isinstance(grader_events, list)

    lines = [
        "# Agent Sandbox Eval Report",
        "",
        f"- Trajectory: `{trajectory_path}`",
        f"- Agent: `{summary['agent']}`",
        f"- Total tasks: {summary['total']}",
        f"- Passed tasks: {summary['passed']}",
        f"- Pass rate: {summary['pass_rate']:.1%}",
        f"- Average score: {summary['average_score']:.2f}",
        f"- Tool calls: {summary['tool_calls']}",
        f"- Average tool calls per task: {summary['avg_tool_calls']:.1f}",
        f"- Average runtime per task: {summary['avg_runtime_ms']:.0f}ms",
        f"- Timeout rate: {summary['timeout_rate']:.1%}",
        f"- Verification rate: {summary['verification_rate']:.1%}",
        f"- Task/grader bug count: {summary['task_or_grader_bug_count']}",
        f"- Model calls: {summary['model_calls']}",
        f"- Input tokens: {summary['input_tokens']}",
        f"- Output tokens: {summary['output_tokens']}",
        f"- Estimated model cost: ${summary['estimated_cost_usd']:.6f}",
        f"- Model cost coverage: {summary['cost_coverage']:.1%}",
        f"- Top failure: `{summary['top_failure'] or 'none'}`",
        "",
        "## Failure Modes",
        "",
    ]
    for name, count in sorted(failures.items()):
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "## Tool Use", ""])
    for name, count in sorted(tool_use.items()):
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "## Tasks", ""])
    for event in grader_events:
        status = "PASS" if event.get("passed") else "FAIL"
        failure = event.get("failure_mode") or ""
        lines.append(f"- `{event.get('task_id')}`: {status} {failure}".rstrip())

    failed_events = [event for event in grader_events if not event.get("passed")]
    if failed_events:
        lines.extend(["", "## Failure Evidence", ""])
        for event in failed_events:
            lines.append(f"### `{event.get('task_id')}`")
            for item in event.get("evidence", [])[:8]:
                cleaned = "\n".join(line.rstrip() for line in str(item).splitlines()).rstrip()
                lines.append(f"- {cleaned}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_markdown_report(trajectory_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_markdown_report(trajectory_path), encoding="utf-8")
    return output_path


def build_comparison_report(trajectory_paths: list[Path]) -> str:
    summaries = [summarize_trajectory(path) for path in trajectory_paths]
    lines = [
        "# Agent Sandbox Eval Comparison",
        "",
        "| Agent | Tasks | Pass Rate | Avg Tool Calls | Model Calls | Tokens | Est. Cost | Avg Runtime | Top Failure | Trajectory |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for summary in summaries:
        typed_summary: dict[str, Any] = summary
        total = int(typed_summary["total"])
        pass_rate = float(typed_summary["pass_rate"])
        avg_tool_calls = float(typed_summary["avg_tool_calls"])
        avg_runtime_ms = float(typed_summary["avg_runtime_ms"])
        model_calls = int(typed_summary["model_calls"])
        total_tokens = int(typed_summary["input_tokens"]) + int(typed_summary["output_tokens"])
        estimated_cost_usd = float(typed_summary["estimated_cost_usd"])
        lines.append(
            "| {agent} | {total} | {pass_rate:.1%} | {avg_tool_calls:.1f} | {model_calls} | {total_tokens} | ${estimated_cost_usd:.6f} | {avg_runtime_ms:.0f}ms | {top_failure} | `{path}` |".format(
                agent=summary["agent"],
                total=total,
                pass_rate=pass_rate,
                avg_tool_calls=avg_tool_calls,
                model_calls=model_calls,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost_usd,
                avg_runtime_ms=avg_runtime_ms,
                top_failure=summary["top_failure"] or "none",
                path=summary["path"],
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def write_comparison_report(trajectory_paths: list[Path], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_comparison_report(trajectory_paths), encoding="utf-8")
    return output_path
