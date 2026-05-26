# Contributing

Agent Sandbox Eval is organized around small, reviewable contributions. The most useful early contributions are benchmark tasks, grader checks, tool implementations, and report improvements. Extensions and task packs can also be distributed as separate Python packages with entry points; see `docs/extensions.md`.

## Development Setup

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m mypy agent_sandbox_eval
```

Docker is required for commands that execute benchmark tasks.

## Adding a Task

1. Create a directory under `benchmarks/<benchmark>/<task-id>/`.
2. Add `task.yaml`.
3. Add a `workspace/` directory with the files the agent should see.
4. Define deterministic `success` criteria.
5. Add `solution.commands` only when the task should be runnable by the `scripted` harness-validation agent.
6. Run:

```bash
ase validate-task benchmarks/<benchmark>/<task-id>/task.yaml
ase validate-tasks --benchmark all
ase run --agent scripted --task-id <task-id>
```

Task success criteria should be deterministic. Do not require network access unless the task explicitly tests network behavior.

## Adding an Agent

Agents implement the `Agent` protocol in `agent_sandbox_eval/agents/base.py`. An agent receives a task, a tool map, and a trajectory recorder. It should not bypass the provided tools to mutate the workspace directly.

## Adding a Tool

Tools should return structured `ToolResult` objects and record both `tool_call` and `tool_result` events. Tool behavior must stay inside the task sandbox unless the tool documentation explicitly states otherwise.

## Quality Gates

Before opening a change:

```bash
python3 -m pytest
python3 -m mypy agent_sandbox_eval
ase list-tasks
ase validate-tasks --benchmark all
```

If Docker is running, also run a small benchmark:

```bash
ase run --agent scripted --benchmark terminal --out runs/scripted-terminal.jsonl
ase report runs/scripted-terminal.jsonl --out reports/scripted-terminal.md
```
