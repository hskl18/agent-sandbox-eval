from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.sandbox.workspace import copy_task_workspace
from agent_sandbox_eval.tools.base import ToolResult


class DockerSandbox:
    def __init__(self, task: Task, image: str = "python:3.13-slim", keep_workspace: bool = False) -> None:
        self.task = task
        self.image = image
        self.keep_workspace = keep_workspace
        self._tempdir: TemporaryDirectory[str] | None = None
        self.workspace: Path | None = None

    def __enter__(self) -> "DockerSandbox":
        self._tempdir = TemporaryDirectory(prefix=f"ase-{self.task.id}-")
        self.workspace = Path(self._tempdir.name) / "workspace"
        copy_task_workspace(self.task.workspace, self.workspace)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self.keep_workspace and self.workspace is not None:
            kept = Path("runs") / "workspaces" / self.task.id
            if kept.exists():
                shutil.rmtree(kept)
            kept.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.workspace, kept)
        if self._tempdir is not None:
            self._tempdir.cleanup()

    def run(self, command: str, timeout_seconds: int | None = None) -> ToolResult:
        if self.workspace is None:
            raise RuntimeError("sandbox has not been entered")
        timeout = timeout_seconds or self.task.limits.timeout_seconds
        docker_command = [
            "docker",
            "run",
            "--rm",
            "--init",
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
        try:
            completed = subprocess.run(
                docker_command,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            return ToolResult(
                stdout=completed.stdout,
                stderr=completed.stderr,
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            stdout = _to_text(exc.stdout)
            stderr = _to_text(exc.stderr)
            return ToolResult(
                stdout=stdout,
                stderr=stderr + f"\nCommand timed out after {timeout}s",
                exit_code=124,
                duration_ms=duration_ms,
            )


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
