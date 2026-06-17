from pathlib import Path

from agent_sandbox_eval.agents.base import AgentContext, AgentResult
from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.runner import Runner


class _ToolInspectingAgent:
    name = "tool-inspector"

    def __init__(self) -> None:
        self.seen_tools: set[str] = set()

    def run(self, context: AgentContext) -> AgentResult:
        self.seen_tools = set(context.tools)
        return AgentResult(final_answer="inspected")


def test_runner_exposes_only_allowed_tools(tmp_path: Path) -> None:
    task = load_task(Path("benchmarks/mcp_like/update-status-001/task.yaml"))
    agent = _ToolInspectingAgent()
    output = tmp_path / "run.jsonl"

    Runner(agent, output_path=output).run([task])

    assert agent.seen_tools == {"mcp_state"}


def test_runner_records_setup_failure_without_running_agent(tmp_path: Path) -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    task = task.__class__(**{**task.__dict__, "setup": ["exit 42"]})
    agent = _ToolInspectingAgent()
    output = tmp_path / "setup-failure.jsonl"

    summary = Runner(agent, output_path=output).run([task])

    assert summary.passed_tasks == 0
    assert agent.seen_tools == set()
    text = output.read_text(encoding="utf-8")
    assert "environment_setup_failure" in text
    assert "Task stopped because setup failed." in text
