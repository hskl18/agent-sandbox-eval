from __future__ import annotations

from dataclasses import dataclass

from agent_sandbox_eval.tools.base import ToolResult


@dataclass(frozen=True)
class FailureAnalysis:
    failure_mode: str
    evidence: list[str]


def analyze_failure(
    agent_tool_results: list[ToolResult],
    grader_result: ToolResult,
    max_tool_calls: int | None = None,
) -> FailureAnalysis:
    combined_all = "\n".join(
        [grader_result.stderr, grader_result.stdout]
        + [result.stderr + "\n" + result.stdout for result in agent_tool_results]
    ).lower()

    evidence = _tool_history_evidence(agent_tool_results)
    evidence.append(f"Final grader exit code: {grader_result.exit_code}")

    if "cannot connect to the docker daemon" in combined_all or "docker daemon" in combined_all:
        evidence.append("Docker daemon was unavailable during task execution or grading.")
        return FailureAnalysis("environment_setup_failure", evidence)

    if grader_result.exit_code == 124 or any(result.exit_code == 124 for result in agent_tool_results):
        evidence.append("A command timed out with exit code 124.")
        return FailureAnalysis("exceeded_budget", evidence)

    if max_tool_calls is not None and len(agent_tool_results) >= max_tool_calls:
        evidence.append(f"Agent reached the max tool-call budget: {max_tool_calls}.")
        return FailureAnalysis("exceeded_budget", evidence)

    if not agent_tool_results:
        evidence.append("Agent made no tool calls before grading.")
        return FailureAnalysis("no_progress", evidence)

    if "not found" in combined_all or "no such file" in combined_all:
        evidence.append("Tool output mentions a missing command, file, flag, package, or path.")
        return FailureAnalysis("command_hallucination", evidence)

    failed_tool_results = [result for result in agent_tool_results if result.exit_code != 0]
    if failed_tool_results:
        evidence.append(f"{len(failed_tool_results)} agent tool call(s) failed before final grading.")
        return FailureAnalysis("incomplete_verification", evidence)

    if any(_looks_like_verification(result) for result in agent_tool_results):
        evidence.append("Agent ran a verification-like command, but the final grader still failed.")
        return FailureAnalysis("regression", evidence)

    evidence.append("Agent tool calls succeeded, but no verification-like command was observed before grading.")
    return FailureAnalysis("incomplete_verification", evidence)


def classify_failure(agent_tool_results: list[ToolResult], grader_result: ToolResult) -> str:
    return analyze_failure(agent_tool_results, grader_result).failure_mode


def _tool_history_evidence(agent_tool_results: list[ToolResult]) -> list[str]:
    if not agent_tool_results:
        return ["Agent tool calls: 0"]

    failed = sum(1 for result in agent_tool_results if result.exit_code != 0)
    timed_out = sum(1 for result in agent_tool_results if result.exit_code == 124)
    evidence = [
        f"Agent tool calls: {len(agent_tool_results)}",
        f"Failed agent tool calls: {failed}",
    ]
    if timed_out:
        evidence.append(f"Timed-out agent tool calls: {timed_out}")
    last = agent_tool_results[-1]
    evidence.append(f"Last agent tool exit code: {last.exit_code}")
    if last.stdout.strip():
        evidence.append(f"Last agent stdout: {last.stdout.strip()[:300]}")
    if last.stderr.strip():
        evidence.append(f"Last agent stderr: {last.stderr.strip()[:300]}")
    return evidence


def _looks_like_verification(result: ToolResult) -> bool:
    text = (result.stdout + "\n" + result.stderr).lower()
    markers = [
        " passed",
        " failed",
        "pytest",
        "unittest",
        "ok",
        "exit code",
    ]
    return any(marker in text for marker in markers)
