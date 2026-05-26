from pathlib import Path

from agent_sandbox_eval.agents.planner import PlannerExecutorAgent
from agent_sandbox_eval.agents.react import ReActAgent
from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.model_providers.local_solution import LocalSolutionProvider
from agent_sandbox_eval.model_providers.base import AgentAction, StepContext
from agent_sandbox_eval.tools.base import ToolResult
from agent_sandbox_eval.trajectories.recorder import TrajectoryRecorder


class _MemoryTool:
    name = "shell"
    description = "memory shell"

    def __init__(self) -> None:
        self.inputs = []

    def run(self, input, context):  # type: ignore[no-untyped-def]
        self.inputs.append(input)
        context.recorder.record("tool_call", context.task.id, tool=self.name, input=input)
        context.recorder.record("tool_result", context.task.id, tool=self.name, output={"exit_code": 0})
        return ToolResult(exit_code=0)


class _Context:
    def __init__(self, task, recorder, tool):  # type: ignore[no-untyped-def]
        self.task = task
        self.recorder = recorder
        self.tools = {"shell": tool}
        self.tool_results = []


class _ObservationProvider:
    name = "observation-provider"

    def __init__(self) -> None:
        self.seen_observations = []

    def plan(self, task):  # type: ignore[no-untyped-def]
        return ["run shell", "finish"]

    def actions(self, task):  # type: ignore[no-untyped-def]
        return []

    def next_action(self, task, context: StepContext):  # type: ignore[no-untyped-def]
        self.seen_observations.append(list(context.observations))
        if context.step_index == 0:
            return AgentAction(kind="tool", tool="shell", input={"cmd": "echo observed"})
        return AgentAction(kind="final", message="observed")


def test_local_solution_provider_builds_actions() -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    provider = LocalSolutionProvider()

    actions = provider.actions(task)

    assert actions[0].kind == "tool"
    assert actions[0].tool == "shell"
    assert actions[-1].kind == "final"


def test_react_agent_executes_provider_actions(tmp_path: Path) -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    tool = _MemoryTool()
    context = _Context(task, TrajectoryRecorder(tmp_path / "react.jsonl", "run"), tool)

    result = ReActAgent(LocalSolutionProvider()).run(context)

    assert "Completed" in result.final_answer
    assert tool.inputs == [{"cmd": "printf 'ready\\n' > answer.txt"}]


def test_planner_agent_records_plan(tmp_path: Path) -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    tool = _MemoryTool()
    path = tmp_path / "planner.jsonl"
    context = _Context(task, TrajectoryRecorder(path, "run"), tool)

    result = PlannerExecutorAgent(LocalSolutionProvider()).run(context)

    assert "Completed" in result.final_answer
    assert "Plan:" in path.read_text(encoding="utf-8")


def test_react_agent_passes_observations_back_to_provider(tmp_path: Path) -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    tool = _MemoryTool()
    provider = _ObservationProvider()
    context = _Context(task, TrajectoryRecorder(tmp_path / "react-observe.jsonl", "run"), tool)

    result = ReActAgent(provider).run(context)

    assert result.final_answer == "observed"
    assert provider.seen_observations[0] == []
    assert provider.seen_observations[1][0]["tool"] == "shell"
    assert provider.seen_observations[1][0]["exit_code"] == 0
