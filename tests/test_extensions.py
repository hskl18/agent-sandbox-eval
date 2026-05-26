from pathlib import Path

from agent_sandbox_eval.agents.base import AgentResult
from agent_sandbox_eval.agents.registry import get_agent, get_provider
from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.extensions import (
    AGENT_ENTRY_POINT_GROUP,
    PROVIDER_ENTRY_POINT_GROUP,
    TASK_PACK_ENTRY_POINT_GROUP,
    TOOL_ENTRY_POINT_GROUP,
    list_all_entry_points,
    load_task_pack_roots,
)
from agent_sandbox_eval.runner import Runner
from agent_sandbox_eval.tools.base import ToolResult


class _FakeEntryPoint:
    def __init__(self, name, group, value, loaded):  # type: ignore[no-untyped-def]
        self.name = name
        self.group = group
        self.value = value
        self._loaded = loaded

    def load(self):  # type: ignore[no-untyped-def]
        return self._loaded


class _EntryPoints(list):
    def select(self, **params):  # type: ignore[no-untyped-def]
        group = params.get("group")
        if group is None:
            return self
        return _EntryPoints([entry for entry in self if entry.group == group])


class _PluginProvider:
    name = "plugin-provider"

    def plan(self, task):  # type: ignore[no-untyped-def]
        return ["finish"]

    def actions(self, task):  # type: ignore[no-untyped-def]
        return []

    def next_action(self, task, context):  # type: ignore[no-untyped-def]
        from agent_sandbox_eval.model_providers.base import AgentAction

        return AgentAction(kind="final", message="plugin final")


class _PluginAgent:
    name = "plugin-agent"

    def __init__(self, provider):  # type: ignore[no-untyped-def]
        self.provider = provider

    def run(self, context):  # type: ignore[no-untyped-def]
        return AgentResult(final_answer=self.provider.next_action(context.task, None).message)


class _PluginTool:
    name = "plugin_tool"
    description = "plugin tool"

    def __init__(self, sandbox):  # type: ignore[no-untyped-def]
        self.sandbox = sandbox

    def run(self, input, context):  # type: ignore[no-untyped-def]
        return ToolResult(stdout="plugin")


def test_extension_entry_points(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    entries = _EntryPoints(
        [
            _FakeEntryPoint("plugin-agent", AGENT_ENTRY_POINT_GROUP, "pkg:agent", _PluginAgent),
            _FakeEntryPoint("plugin-provider", PROVIDER_ENTRY_POINT_GROUP, "pkg:provider", _PluginProvider),
            _FakeEntryPoint("plugin-tool", TOOL_ENTRY_POINT_GROUP, "pkg:tool", lambda sandbox: _PluginTool(sandbox)),
            _FakeEntryPoint("plugin-pack", TASK_PACK_ENTRY_POINT_GROUP, "pkg:tasks", lambda: "extra-benchmarks"),
        ]
    )
    monkeypatch.setattr("importlib.metadata.entry_points", lambda **kwargs: entries.select(**kwargs))

    provider = get_provider("plugin-provider")
    agent = get_agent("plugin-agent", provider_name="plugin-provider")
    groups = list_all_entry_points()

    assert provider.name == "plugin-provider"
    assert agent.name == "plugin-agent"
    assert groups[TOOL_ENTRY_POINT_GROUP][0].name == "plugin-tool"
    assert load_task_pack_roots()["plugin-pack"] == "extra-benchmarks"


def test_runner_accepts_extra_tool_factories(tmp_path: Path) -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    output = tmp_path / "run.jsonl"
    runner = Runner(
        agent=get_agent("noop"),
        output_path=output,
        extra_tool_factories={"plugin_tool": lambda sandbox: _PluginTool(sandbox)},
    )

    summary = runner.run([task])

    assert summary.total_tasks == 1
