from __future__ import annotations

import shutil
from pathlib import Path


def copy_task_workspace(source: Path, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination

