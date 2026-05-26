from pathlib import Path
from subprocess import CompletedProcess

from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.sandbox.docker import DockerSandbox


def test_docker_sandbox_runs_as_host_user(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(command)
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.os.getuid", lambda: 1234)
    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.os.getgid", lambda: 5678)
    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", fake_run)

    sandbox = DockerSandbox(task)
    sandbox.workspace = tmp_path

    result = sandbox.run("python -c 'print(1)'")

    assert result.exit_code == 0
    assert commands
    assert commands[0][commands[0].index("--user") + 1] == "1234:5678"
    assert commands[0][commands[0].index("--env") + 1] == "HOME=/tmp"
