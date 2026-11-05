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


def _fake_docker(
    monkeypatch, removal_results: list[CompletedProcess]  # type: ignore[no-untyped-def]
) -> list[list[str]]:
    commands: list[list[str]] = []
    remaining = iter(removal_results)

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(command)
        if command[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"partial")
        return next(remaining)

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", fake_run)
    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.time.sleep", lambda _: None)
    return commands


def _removal(returncode: int, stderr: str = "") -> CompletedProcess:
    return CompletedProcess([], returncode, stdout="", stderr=stderr)


def test_timeout_removes_the_container_it_started(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    commands = _fake_docker(monkeypatch, [_removal(0)])
    sandbox = DockerSandbox(task)
    sandbox.workspace = tmp_path

    result = sandbox.run("sleep 60", timeout_seconds=1)

    name = commands[0][commands[0].index("--name") + 1]
    assert commands[1] == ["docker", "rm", "--force", name]
    assert result.exit_code == 124
    assert result.stdout == "partial"
    assert "timed out after 1s" in result.stderr


def test_timeout_retries_until_the_container_is_gone(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    commands = _fake_docker(
        monkeypatch,
        [
            _removal(1, "removal of container ase-x is already in progress"),
            _removal(1, "Error response from daemon: No such container: ase-x"),
        ],
    )
    sandbox = DockerSandbox(task)
    sandbox.workspace = tmp_path

    result = sandbox.run("sleep 60", timeout_seconds=1)

    assert len(commands) == 3
    assert result.exit_code == 124


def test_unconfirmed_removal_stops_the_run_and_skips_the_export(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml").resolve())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.CONTAINER_REMOVAL_SECONDS", 0)
    commands = _fake_docker(monkeypatch, [_removal(1, "Cannot connect to the Docker daemon")])

    with pytest.raises(RuntimeError, match="Cannot connect to the Docker daemon"):
        with DockerSandbox(task, keep_workspace=True) as sandbox:
            sandbox.run("sleep 60", timeout_seconds=1)

    assert commands[0][commands[0].index("--name") + 1] in commands[1]
    assert not (tmp_path / "runs").exists()


def test_keep_workspace_does_not_copy_symlink_targets(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml").resolve())
    monkeypatch.chdir(tmp_path)
    outside = tmp_path / "secret.txt"
    outside.write_text("host secret", encoding="utf-8")

    with DockerSandbox(task, keep_workspace=True) as sandbox:
        assert sandbox.workspace is not None
        (sandbox.workspace / "leak.txt").symlink_to(outside)

    assert (tmp_path / "runs" / "workspaces" / task.id / "leak.txt").is_symlink()


def test_timeout_stops_a_real_container(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    _skip_without_docker()
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    real_run = subprocess.run
    names: list[str] = []

    def recording_run(command, **kwargs):  # type: ignore[no-untyped-def]
        if command[:2] == ["docker", "run"]:
            names.append(command[command.index("--name") + 1])
        return real_run(command, **kwargs)

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", recording_run)
    sandbox = DockerSandbox(task)
    sandbox.workspace = tmp_path

    # Pull the image first, so the timeout below can only fire on the running command.
    assert sandbox.run("true").exit_code == 0
    result = sandbox.run("touch started && sleep 300", timeout_seconds=10)

    assert result.exit_code == 124
    assert (tmp_path / "started").exists()
    listed = real_run(
        ["docker", "ps", "--all", "--quiet", "--filter", f"name={names[-1]}"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert listed.stdout.strip() == ""


def _docker_with_status(
    monkeypatch, status: int, removal: CompletedProcess  # type: ignore[no-untyped-def]
) -> list[list[str]]:
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(command)
        if command[:2] == ["docker", "run"]:
            return CompletedProcess(command, status, stdout="", stderr="")
        return removal

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", fake_run)
    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.time.sleep", lambda _: None)
    return commands


def test_ordinary_status_still_removes_the_container(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml").resolve())
    monkeypatch.chdir(tmp_path)
    commands = _docker_with_status(monkeypatch, 1, _removal(0))

    with DockerSandbox(task, keep_workspace=True) as sandbox:
        assert sandbox.run("exit 1").exit_code == 1

    assert commands[1] == ["docker", "rm", "--force", commands[0][commands[0].index("--name") + 1]]
    assert (tmp_path / "runs" / "workspaces" / task.id).exists()


def test_docker_failure_with_no_container_still_exports(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml").resolve())
    monkeypatch.chdir(tmp_path)
    _docker_with_status(monkeypatch, 125, _removal(1, "Error: No such container: ase-x"))

    with DockerSandbox(task, keep_workspace=True) as sandbox:
        assert sandbox.run("true").exit_code == 125

    assert (tmp_path / "runs" / "workspaces" / task.id).exists()


@pytest.mark.parametrize("status", [-9, 0, 1, 125])
def test_other_statuses_require_confirmed_removal(monkeypatch, tmp_path: Path, status: int) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.CONTAINER_REMOVAL_SECONDS", 0)
    _docker_with_status(monkeypatch, status, _removal(1, "daemon is busy"))
    sandbox = DockerSandbox(task)
    sandbox.workspace = tmp_path

    with pytest.raises(RuntimeError, match="daemon is busy"):
        sandbox.run("true")


def test_later_success_does_not_clear_an_earlier_unresolved_container(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml").resolve())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.CONTAINER_REMOVAL_SECONDS", 0)
    run_statuses = iter([1, 0])
    removals = iter([_removal(1, "Cannot connect to the Docker daemon"), _removal(0)])

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        if command[:2] == ["docker", "run"]:
            return CompletedProcess(command, next(run_statuses), stdout="", stderr="")
        return next(removals)

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", fake_run)

    with DockerSandbox(task, keep_workspace=True) as sandbox:
        with pytest.raises(RuntimeError, match="could not confirm"):
            sandbox.run("true")
        assert sandbox.run("true").exit_code == 0

    assert not (tmp_path / "runs").exists()


def test_missing_docker_cli_started_nothing(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml").resolve())
    monkeypatch.chdir(tmp_path)
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(command)
        raise FileNotFoundError("docker")

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", fake_run)

    with pytest.raises(FileNotFoundError):
        with DockerSandbox(task, keep_workspace=True) as sandbox:
            sandbox.run("true")

    assert len(commands) == 1
    assert (tmp_path / "runs" / "workspaces" / task.id).exists()


def test_docker_cli_lost_during_cleanup_is_not_a_confirmation(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.CONTAINER_REMOVAL_SECONDS", 0)

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        if command[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        raise FileNotFoundError("docker")

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", fake_run)
    sandbox = DockerSandbox(task)
    sandbox.workspace = tmp_path

    with pytest.raises(RuntimeError, match="could not confirm"):
        sandbox.run("sleep 60", timeout_seconds=1)


def test_interrupted_cleanup_skips_the_export(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml").resolve())
    monkeypatch.chdir(tmp_path)

    def interrupted(command, **kwargs):  # type: ignore[no-untyped-def]
        raise KeyboardInterrupt

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", interrupted)

    with pytest.raises(KeyboardInterrupt):
        with DockerSandbox(task, keep_workspace=True) as sandbox:
            sandbox.run("sleep 60")

    assert not (tmp_path / "runs").exists()


def test_interrupted_command_removes_its_container(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(command)
        if command[:2] == ["docker", "run"]:
            raise KeyboardInterrupt
        return _removal(0)

    monkeypatch.setattr("agent_sandbox_eval.sandbox.docker.subprocess.run", fake_run)
    sandbox = DockerSandbox(task)
    sandbox.workspace = tmp_path

    with pytest.raises(KeyboardInterrupt):
        sandbox.run("sleep 60")

    assert commands[1] == ["docker", "rm", "--force", commands[0][commands[0].index("--name") + 1]]
