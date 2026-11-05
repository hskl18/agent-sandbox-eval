from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.sandbox.workspace import copy_task_workspace
from agent_sandbox_eval.tools.base import ToolResult


CONTAINER_REMOVAL_SECONDS = 30


class DockerSandbox:
    def __init__(self, task: Task, image: str = "python:3.13-slim", keep_workspace: bool = False) -> None:
        self.task = task
        self.image = image
        self.keep_workspace = keep_workspace
        self._tempdir: TemporaryDirectory[str] | None = None
        self.workspace: Path | None = None
        self._unresolved_containers: set[str] = set()

    def __enter__(self) -> "DockerSandbox":
        self._tempdir = TemporaryDirectory(prefix=f"ase-{self.task.id}-")
        self.workspace = Path(self._tempdir.name) / "workspace"
        copy_task_workspace(self.task.workspace, self.workspace)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        # A live container could swap files in mid-copy, so nothing leaves the workspace in that state.
        if self.keep_workspace and self.workspace is not None and not self._unresolved_containers:
            kept = Path("runs") / "workspaces" / self.task.id
            if kept.exists():
                shutil.rmtree(kept)
            kept.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.workspace, kept, symlinks=True)
        if self._tempdir is not None:
            self._tempdir.cleanup()

    def run(self, command: str, timeout_seconds: int | None = None) -> ToolResult:
        if self.workspace is None:
            raise RuntimeError("sandbox has not been entered")
        timeout = timeout_seconds or self.task.limits.timeout_seconds
        container_name = f"ase-{uuid.uuid4().hex}"
        docker_command = [
            "docker",
            "run",
            "--rm",
            "--init",
            "--name",
            container_name,
            "--network",
            "bridge" if self.task.limits.network else "none",
            "--user",
            _host_user(),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges=true",
            "--security-opt",
            "seccomp=builtin",
            "--pids-limit",
            str(self.task.limits.pids_limit),
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777",
            "--env",
            "HOME=/tmp",
            "--memory",
            f"{self.task.limits.memory_mb}m",
            "--cpus",
            str(self.task.limits.cpus),
            "-v",
            f"{self.workspace.resolve()}:/workspace:rw",
            "-w",
            "/workspace",
            self.image,
            "sh",
            "-lc",
            command,
        ]
        started = time.monotonic()
        self._unresolved_containers.add(container_name)
        try:
            completed = subprocess.run(
                docker_command,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            self._remove_container(container_name)
            stdout = _to_text(exc.stdout)
            stderr = _to_text(exc.stderr)
            return ToolResult(
                stdout=stdout,
                stderr=stderr + f"\nCommand timed out after {timeout}s",
                exit_code=124,
                duration_ms=duration_ms,
            )
        except FileNotFoundError:
            # Without a docker CLI, this docker run started nothing.
            self._unresolved_containers.discard(container_name)
            raise
        except BaseException:
            self._remove_container(container_name)
            raise
        duration_ms = int((time.monotonic() - started) * 1000)
        # An ordinary status does not prove the container ended, because a lost attach connection also returns 1.
        self._remove_container(container_name)
        return ToolResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _remove_container(self, name: str) -> None:
        deadline = time.monotonic() + CONTAINER_REMOVAL_SECONDS
        while True:
            try:
                removal = subprocess.run(
                    ["docker", "rm", "--force", name],
                    text=True,
                    capture_output=True,
                    timeout=CONTAINER_REMOVAL_SECONDS,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                error = str(exc)
            else:
                if removal.returncode == 0 or "no such container" in removal.stderr.lower():
                    self._unresolved_containers.discard(name)
                    return
                error = removal.stderr.strip()
            if time.monotonic() >= deadline:
                raise RuntimeError(f"could not confirm that container {name} stopped: {error}")
            time.sleep(0.5)


def _to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _host_user() -> str:
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if getuid is None or getgid is None:
        return "1000:1000"
    return f"{getuid()}:{getgid()}"
