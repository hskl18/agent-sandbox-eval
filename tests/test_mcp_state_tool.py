import os
from pathlib import Path

import pytest

from agent_sandbox_eval.sandbox.workspace import WorkspaceValidationError
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



def _symlinked_state(tmp_path: Path, target: Path) -> tuple[MCPStateTool, _Context]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "state.json").symlink_to(target)
    return MCPStateTool(workspace), _Context(TrajectoryRecorder(tmp_path / "run.jsonl", "run"))


def test_mcp_state_tool_refuses_a_symlink_to_a_host_file(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text('{"secret": "host"}\n', encoding="utf-8")
    tool, context = _symlinked_state(tmp_path, outside)

    with pytest.raises(WorkspaceValidationError):
        tool.run({"action": "get"}, context)
    with pytest.raises(WorkspaceValidationError):
        tool.run({"action": "set", "key": "secret", "value": "overwritten"}, context)

    assert outside.read_text(encoding="utf-8") == '{"secret": "host"}\n'


def test_mcp_state_tool_does_not_write_through_a_dangling_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "created-outside.json"
    tool, context = _symlinked_state(tmp_path, outside)

    with pytest.raises(WorkspaceValidationError):
        tool.run({"action": "set", "key": "status", "value": "done"}, context)
    # set reads first, so the writer needs its own check.
    with pytest.raises(WorkspaceValidationError):
        tool._write_state({"status": "done"})

    assert not outside.exists()


def test_mcp_state_tool_does_not_hang_on_a_fifo(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "state.json")
    context = _Context(TrajectoryRecorder(tmp_path / "run.jsonl", "run"))

    with pytest.raises(WorkspaceValidationError):
        MCPStateTool(tmp_path).run({"action": "get"}, context)
