from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from agent_sandbox_eval.agents.base import Agent, AgentContext
from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.eval.grader import Grader
from agent_sandbox_eval.eval.metrics import RunSummary
from agent_sandbox_eval.sandbox.docker import DockerSandbox
from agent_sandbox_eval.tools.files import FileReadTool, FileWriteTool
from agent_sandbox_eval.tools.mcp_state import MCPStateTool
from agent_sandbox_eval.tools.python import PythonTool
from agent_sandbox_eval.tools.shell import ShellTool
from agent_sandbox_eval.tools.base import ToolResult
from agent_sandbox_eval.trajectories.recorder import TrajectoryRecorder

ToolFactory = Callable[[DockerSandbox], object]


class Runner:
    def __init__(
        self,
        agent: Agent,
        output_path: Path,
        docker_image: str = "python:3.13-slim",
        keep_workspaces: bool = False,
        extra_tool_factories: dict[str, ToolFactory] | None = None,
    ) -> None:
        self.agent = agent
        self.output_path = output_path
        self.docker_image = docker_image
        self.keep_workspaces = keep_workspaces
        self.extra_tool_factories = extra_tool_factories or {}
        self.grader = Grader()

    def run(self, tasks: list[Task]) -> RunSummary:
        run_id = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ") + f"-{self.agent.name}"
        recorder = TrajectoryRecorder(self.output_path, run_id)
        recorder.record("run_start", agent=self.agent.name, task_count=len(tasks))
        passed = 0

        for task in tasks:
            recorder.record(
                "task_start",
                task.id,
                agent=self.agent.name,
                title=task.title,
                benchmark=task.benchmark,
                success_type=task.success.type,
                success_command=task.success.command,
            )
            agent_tool_results = []
            with DockerSandbox(task, image=self.docker_image, keep_workspace=self.keep_workspaces) as sandbox:
                setup_context = _ToolAgentContext(task, {}, recorder, "setup")
                shell = ShellTool(sandbox)
                for command in task.setup:
                    setup_result = shell.run({"cmd": command}, setup_context)
                    agent_tool_results.append(setup_result)

                if sandbox.workspace is None:
                    raise RuntimeError("sandbox workspace was not initialized")
                tools = {
                    "shell": ShellTool(sandbox),
                    "file_read": FileReadTool(sandbox.workspace),
                    "file_write": FileWriteTool(sandbox.workspace),
                    "python": PythonTool(sandbox),
                    "mcp_state": MCPStateTool(sandbox.workspace),
                }
                for name, factory in self.extra_tool_factories.items():
                    tools[name] = factory(sandbox)
                context = _ToolAgentContext(task, tools, recorder, self.agent.name)
                agent_result = self.agent.run(context)

                # Capture shell/python tool results for failure analysis.
                agent_tool_results.extend(context.tool_results)
                grade = self.grader.grade(task, sandbox, agent_tool_results)
                if grade.passed:
                    passed += 1
                recorder.record(
                    "grader_result",
                    task.id,
                    agent=self.agent.name,
                    passed=grade.passed,
                    score=grade.score,
                    failure_mode=grade.failure_mode,
                    evidence=grade.evidence,
                    raw_result=grade.raw_result.to_dict(),
                )
                recorder.record("task_end", task.id, agent=self.agent.name, final_answer=agent_result.final_answer)

        recorder.record("run_end", agent=self.agent.name, passed_tasks=passed, total_tasks=len(tasks))
        return RunSummary(total_tasks=len(tasks), passed_tasks=passed)


class _ToolAgentContext(AgentContext):
    tools_agent_name: str
    tool_results: list[ToolResult]

    def __init__(self, task, tools, recorder, tools_agent_name):  # type: ignore[no-untyped-def]
        super().__init__(task=task, tools=tools, recorder=recorder)
        object.__setattr__(self, "tools_agent_name", tools_agent_name)
        object.__setattr__(self, "tool_results", [])
