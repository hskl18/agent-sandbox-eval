from pathlib import Path

from agent_sandbox_eval.benchmarks.loader import benchmark_roots, discover_task_files, load_benchmark, load_task


def test_load_task() -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    assert task.schema_version == 1
    assert task.id == "pass-command-001"
    assert task.success.command
    assert task.workspace.exists()


def test_discover_benchmark_tasks() -> None:
    paths = discover_task_files(Path("benchmarks"), "terminal")
    assert len(paths) >= 2


def test_load_benchmark() -> None:
    tasks = load_benchmark("terminal", Path("benchmarks"))
    assert len(tasks) == 16
    assert {task.id for task in tasks} >= {"pass-command-001", "fix-config-001"}


def test_load_all_benchmarks() -> None:
    tasks = load_benchmark("all", Path("benchmarks"))
    by_benchmark = {}
    for task in tasks:
        by_benchmark[task.benchmark] = by_benchmark.get(task.benchmark, 0) + 1

    assert by_benchmark == {"mcp_like": 3, "swe_lite": 6, "terminal": 16}


def test_rejects_unsupported_task_schema_version(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest = tmp_path / "task.yaml"
    manifest.write_text(
        """
schema_version: 999
id: bad
benchmark: terminal
title: Bad
instruction: Bad schema.
workspace: workspace
success:
  type: command
  command: "true"
""".strip(),
        encoding="utf-8",
    )

    try:
        load_task(manifest)
    except ValueError as exc:
        assert "unsupported task schema_version" in str(exc)
    else:
        raise AssertionError("expected unsupported schema version to fail")


def test_rejects_solution_tool_outside_allowed_tools(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest = tmp_path / "task.yaml"
    manifest.write_text(
        """
schema_version: 1
id: bad-tools
benchmark: terminal
title: Bad tools
instruction: Bad tool policy.
workspace: workspace
allowed_tools: [mcp_state]
success:
  type: command
  command: "true"
solution:
  commands:
    - "true"
""".strip(),
        encoding="utf-8",
    )

    try:
        load_task(manifest)
    except ValueError as exc:
        assert "solution.commands require shell" in str(exc)
    else:
        raise AssertionError("expected disallowed solution tool to fail")


def test_benchmark_roots_include_task_pack_entry_points(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from agent_sandbox_eval.extensions import TASK_PACK_ENTRY_POINT_GROUP

    class FakeEntryPoint:
        name = "pack"
        group = TASK_PACK_ENTRY_POINT_GROUP
        value = "pkg:pack"

        def load(self):  # type: ignore[no-untyped-def]
            return lambda: pack_root

    class EntryPoints(list):
        def select(self, **params):  # type: ignore[no-untyped-def]
            group = params.get("group")
            if group is None:
                return self
            return EntryPoints([entry for entry in self if entry.group == group])

    pack_root = tmp_path / "pack"
    pack_root.mkdir()
    entries = EntryPoints([FakeEntryPoint()])
    monkeypatch.setattr("importlib.metadata.entry_points", lambda **kwargs: entries.select(**kwargs))

    roots = benchmark_roots(Path("benchmarks"))

    assert pack_root in roots
