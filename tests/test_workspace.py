from __future__ import annotations

from pathlib import Path

import pytest

from agent_sandbox_eval.sandbox.workspace import WorkspaceValidationError, copy_task_workspace


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
