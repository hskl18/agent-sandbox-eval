from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_sandbox_eval.sandbox.workspace import (
    WorkspaceValidationError,
    copy_task_workspace,
    read_workspace_text,
    write_workspace_text,
)
from agent_sandbox_eval.tools.files import FileReadTool, FileWriteTool


def test_workspace_copy_preserves_snapshotted_bytes_and_permissions(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    nested = workspace / "nested"
    nested.mkdir(parents=True)
    source = nested / "run.sh"
    source.write_text("#!/bin/sh\necho ready\n", encoding="utf-8")
    source.chmod(0o751)
    destination = tmp_path / "copied"

    copy_task_workspace(workspace, destination)

    copied = destination / "nested" / "run.sh"
    assert copied.read_bytes() == b"#!/bin/sh\necho ready\n"
    assert copied.stat().st_mode & 0o777 == 0o751


@pytest.mark.parametrize("link_kind", ["internal", "external", "broken", "cycle"])
def test_workspace_copy_rejects_symlinks_without_dereferencing(
    tmp_path: Path,
    link_kind: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    destination = tmp_path / "copied"
    if link_kind == "internal":
        (workspace / "target.txt").write_text("inside\n", encoding="utf-8")
        (workspace / "input.txt").symlink_to("target.txt")
    elif link_kind == "external":
        external = tmp_path / "external.txt"
        external.write_text("outside\n", encoding="utf-8")
        (workspace / "input.txt").symlink_to(external)
    elif link_kind == "broken":
        (workspace / "input.txt").symlink_to("missing.txt")
    else:
        (workspace / "loop").symlink_to(".", target_is_directory=True)

    with pytest.raises(WorkspaceValidationError, match="symbolic links are not supported"):
        copy_task_workspace(workspace, destination)
    assert not destination.exists()


def test_workspace_text_helpers_overwrite_regular_files(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"

    write_workspace_text(path, "a longer first version\n")
    write_workspace_text(path, "second\n")

    assert read_workspace_text(path) == "second\n"


def test_workspace_text_helpers_refuse_symlinks(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("keep\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(outside)

    with pytest.raises(WorkspaceValidationError, match="regular file"):
        read_workspace_text(link)
    with pytest.raises(WorkspaceValidationError, match="regular file"):
        write_workspace_text(link, "overwritten\n")

    assert outside.read_text(encoding="utf-8") == "keep\n"


def test_file_tools_do_not_hang_on_a_fifo(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "pipe")

    with pytest.raises(WorkspaceValidationError, match="regular file"):
        FileReadTool(tmp_path).run({"path": "pipe"}, None)
    with pytest.raises(WorkspaceValidationError, match="regular file"):
        FileWriteTool(tmp_path).run({"path": "pipe", "content": "x"}, None)
