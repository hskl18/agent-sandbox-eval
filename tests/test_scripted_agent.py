from pathlib import Path
import subprocess

import pytest

from agent_sandbox_eval.agents.scripted import ScriptedAgent
from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.runner import Runner


def test_scripted_agent_can_use_mcp_state_tool(tmp_path: Path) -> None:
    docker = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
    if docker.returncode != 0:
        pytest.skip("Docker daemon is not available")

    task = load_task(Path("benchmarks/mcp_like/update-status-001/task.yaml"))
    output = tmp_path / "run.jsonl"
    summary = Runner(ScriptedAgent(), output_path=output).run([task])

    assert summary.passed_tasks == 1
    assert '"tool": "mcp_state"' in output.read_text(encoding="utf-8")
