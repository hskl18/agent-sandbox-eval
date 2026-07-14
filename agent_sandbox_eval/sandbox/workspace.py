from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path
from typing import Any


class WorkspaceValidationError(ValueError):
    pass


def snapshot_task_workspace(source: Path) -> list[dict[str, Any]]:
    try:
        root_stat = os.lstat(source)
    except OSError as exc:
        raise WorkspaceValidationError(f"task workspace is unreadable: {source}: {exc}") from exc
    if stat.S_ISLNK(root_stat.st_mode):
        raise WorkspaceValidationError(f"task workspace root cannot be a symbolic link: {source}")
    if not stat.S_ISDIR(root_stat.st_mode):
        raise WorkspaceValidationError(f"task workspace root must be a directory: {source}")
    entries: list[dict[str, Any]] = [_directory_identity(".", root_stat)]
    _snapshot_directory(source, source, entries)
    return entries


def _snapshot_directory(
    root: Path,
    directory: Path,
    entries: list[dict[str, Any]],
) -> None:
    try:
        with os.scandir(directory) as scanner:
            children = sorted(scanner, key=lambda entry: entry.name)
    except OSError as exc:
        raise WorkspaceValidationError(f"task workspace directory is unreadable: {directory}: {exc}") from exc
    for child in children:
        path = Path(child.path)
        relative = path.relative_to(root).as_posix()
        try:
            metadata = child.stat(follow_symlinks=False)
        except OSError as exc:
            raise WorkspaceValidationError(f"task workspace entry is unreadable: {relative}: {exc}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            try:
                target = os.readlink(path)
            except OSError as exc:
                raise WorkspaceValidationError(
                    f"task workspace symbolic link is unreadable: {relative}: {exc}"
                ) from exc
            raise WorkspaceValidationError(
                f"task workspace symbolic links are not supported: {relative} -> {target}"
            )
        if stat.S_ISDIR(metadata.st_mode):
            entries.append(_directory_identity(relative, metadata))
            _snapshot_directory(root, path, entries)
            continue
        if stat.S_ISREG(metadata.st_mode):
            entries.append(_file_identity(path, relative))
            continue
        raise WorkspaceValidationError(
            f"task workspace contains an unsupported special file: {relative}"
        )


def _directory_identity(relative: str, metadata: os.stat_result) -> dict[str, Any]:
    return {
        "path": relative,
        "type": "directory",
        "mode": stat.S_IMODE(metadata.st_mode),
        "mtime_ns": metadata.st_mtime_ns,
    }


def _file_identity(path: Path, relative: str) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkspaceValidationError(f"task workspace file is unreadable: {relative}: {exc}") from exc
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        with os.fdopen(descriptor, "rb", closefd=False) as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable_fields = ("st_mode", "st_size", "st_mtime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
        raise WorkspaceValidationError(f"task workspace file changed while hashing: {relative}")
    if not stat.S_ISREG(after.st_mode):
        raise WorkspaceValidationError(f"task workspace entry changed type while hashing: {relative}")
    return {
        "path": relative,
        "type": "file",
        "mode": stat.S_IMODE(after.st_mode),
        "size": after.st_size,
        "mtime_ns": after.st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


def copy_task_workspace(source: Path, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    source_identity = snapshot_task_workspace(source)
    try:
        shutil.copytree(source, destination, symlinks=True)
        copied_identity = snapshot_task_workspace(destination)
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise
    if copied_identity != source_identity:
        shutil.rmtree(destination)
        raise WorkspaceValidationError("task workspace changed while it was being copied")
    return destination
