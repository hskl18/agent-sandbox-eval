from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any, Callable


AGENT_ENTRY_POINT_GROUP = "agent_sandbox_eval.agents"
PROVIDER_ENTRY_POINT_GROUP = "agent_sandbox_eval.providers"
TOOL_ENTRY_POINT_GROUP = "agent_sandbox_eval.tools"
TASK_PACK_ENTRY_POINT_GROUP = "agent_sandbox_eval.task_packs"


@dataclass(frozen=True)
class ExtensionSpec:
    name: str
    group: str
    value: str
    distribution: str | None = None
    version: str | None = None


def load_entry_point(group: str, name: str) -> Callable[..., Any] | None:
    for entry_point in metadata.entry_points(group=group):
        if entry_point.name == name:
            loaded = entry_point.load()
            if not callable(loaded):
                raise TypeError(f"entry point {group}:{name} did not load a callable")
            return loaded
    return None


def list_entry_points(group: str) -> list[ExtensionSpec]:
    return [
        ExtensionSpec(
            name=entry_point.name,
            group=group,
            value=entry_point.value,
            distribution=getattr(getattr(entry_point, "dist", None), "name", None),
            version=getattr(getattr(entry_point, "dist", None), "version", None),
        )
        for entry_point in metadata.entry_points(group=group)
    ]


def list_all_entry_points() -> dict[str, list[ExtensionSpec]]:
    return {
        AGENT_ENTRY_POINT_GROUP: list_entry_points(AGENT_ENTRY_POINT_GROUP),
        PROVIDER_ENTRY_POINT_GROUP: list_entry_points(PROVIDER_ENTRY_POINT_GROUP),
        TOOL_ENTRY_POINT_GROUP: list_entry_points(TOOL_ENTRY_POINT_GROUP),
        TASK_PACK_ENTRY_POINT_GROUP: list_entry_points(TASK_PACK_ENTRY_POINT_GROUP),
    }


def load_task_pack_roots() -> dict[str, Any]:
    roots: dict[str, Any] = {}
    for entry_point in metadata.entry_points(group=TASK_PACK_ENTRY_POINT_GROUP):
        loaded = entry_point.load()
        roots[entry_point.name] = loaded() if callable(loaded) else loaded
    return roots
