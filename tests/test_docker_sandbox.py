from dataclasses import replace
from pathlib import Path
import subprocess
from subprocess import CompletedProcess

import pytest

from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.sandbox.docker import DockerSandbox


def _skip_without_docker() -> None:
    docker = subprocess.run(
        ["docker", "info"], capture_output=True, text=True, check=False
    )
    if docker.returncode != 0:
        pytest.skip("Docker daemon is not available")


def test_docker_sandbox_uses_hardened_runtime_defaults(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
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
    assert commands[0][commands[0].index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges=true" in commands[0]
    assert "seccomp=builtin" in commands[0]
    assert "--read-only" in commands[0]
    assert commands[0][commands[0].index("--pids-limit") + 1] == "256"
    assert commands[0][commands[0].index("--tmpfs") + 1] == (
        "/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777"
    )
    assert commands[0][commands[0].index("-v") + 1] == f"{tmp_path.resolve()}:/workspace:rw"


def test_docker_sandbox_applies_task_pid_limit(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    task = replace(task, limits=replace(task.limits, pids_limit=32))
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(command)
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", fake_run)

    sandbox = DockerSandbox(task)
    sandbox.workspace = tmp_path
    result = sandbox.run("true")

    assert result.exit_code == 0
    assert commands[0][commands[0].index("--pids-limit") + 1] == "32"


@pytest.mark.parametrize(
    "hostile",
    [
        "true --privileged --security-opt seccomp=unconfined",
        "touch /etc/agent-sandbox-eval-hostile-write",
        "while :; do sh -c 'sleep 60' & done",
    ],
)
def test_hardened_runtime_flags_wrap_hostile_commands(
    monkeypatch, tmp_path: Path, hostile: str
) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(command)
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", fake_run)

    sandbox = DockerSandbox(task)
    sandbox.workspace = tmp_path
    result = sandbox.run(hostile)

    assert result.exit_code == 0
    assert "--init" in commands[0]
    assert commands[0][-4:] == ["python:3.13-slim", "sh", "-lc", hostile]
    assert commands[0].count("--security-opt") == 2
    assert commands[0][commands[0].index("--cap-drop") + 1] == "ALL"
    assert commands[0][commands[0].index("--pids-limit") + 1] == "256"


def test_read_only_root_and_writable_tmp_are_enforced(tmp_path: Path) -> None:
    _skip_without_docker()
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))

    sandbox = DockerSandbox(task)
    sandbox.workspace = tmp_path

    root_write = sandbox.run("touch /etc/agent-sandbox-eval-write-test")
    tmp_write = sandbox.run("touch /tmp/write-test && test -f /tmp/write-test")

    assert root_write.exit_code != 0
    assert tmp_write.exit_code == 0
