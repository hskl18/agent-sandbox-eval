from pathlib import Path

from agent_sandbox_eval.tools.mcp_state import MCPStateTool
from agent_sandbox_eval.trajectories.recorder import TrajectoryRecorder


class _Task:
    id = "state-task"


class _Context:
    task = _Task()

    def __init__(self, recorder: TrajectoryRecorder) -> None:
        self.recorder = recorder


def test_mcp_state_tool_get_and_set(tmp_path: Path) -> None:
    recorder = TrajectoryRecorder(tmp_path / "run.jsonl", "run")
    context = _Context(recorder)
    tool = MCPStateTool(tmp_path)

    set_result = tool.run({"action": "set", "key": "status", "value": "done"}, context)
    get_result = tool.run({"action": "get", "key": "status"}, context)

    assert set_result.exit_code == 0
    assert get_result.stdout == '"done"'
    assert (tmp_path / "state.json").exists()

