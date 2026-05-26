# Agent Sandbox Eval

Agent Sandbox Eval is a local-first framework for evaluating tool-using AI agents in reproducible Docker sandboxes. It provides task manifests, sandboxed execution, JSONL trajectory recording, deterministic grading, replay, and Markdown reports.

This repository is currently in the early MVP stage described in [`proposal.md`](proposal.md).

## Quickstart

```bash
python3 -m pip install -e .
ase list-tasks
ase run --agent react --provider local-solution --benchmark all --out runs/react-all.jsonl
ase run --agent planner --provider local-solution --benchmark all --out runs/planner-all.jsonl
ase run --agent scripted --benchmark all --out runs/scripted-all.jsonl
ase report runs/scripted-all.jsonl --out reports/scripted-all.md
ase compare runs/react-all.jsonl runs/planner-all.jsonl runs/scripted-all.jsonl --out reports/compare.md
ase replay runs/react-all.jsonl --task pass-command-001
```

The default provider for `react` and `planner` is `local-solution`, a deterministic provider that converts bundled solution metadata into tool actions. It exists so agent loops can be tested before external model providers are added.

## Development

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m mypy agent_sandbox_eval
ase validate-tasks --benchmark all
```

Docker is required for `ase run`.

## Bundled Benchmarks

The current repository includes:

- 16 terminal tasks.
- 6 SWE-lite tasks.
- 3 MCP-like state-tool tasks.

The `scripted` agent is expected to pass every bundled task. This validates task manifests, sandbox execution, trajectory recording, grading, reports, and replay without depending on a model provider.

Failure reports include deterministic failure modes and evidence. See [docs/failure-analysis.md](docs/failure-analysis.md).

Agents, model providers, tools, and benchmark task packs can be extended through Python entry points. See [docs/extensions.md](docs/extensions.md).

Reproducible example commands are listed in [examples/README.md](examples/README.md).

## Current Agent Status

- `scripted`: executes task-provided validation solutions directly.
- `noop`: performs no tool calls and is useful for negative harness tests.
- `react`: runs a ReAct-style tool loop over provider actions.
- `planner`: records a plan, then executes provider actions step by step.
- `local-solution`: deterministic provider for local validation without API keys.
- `openai-responses`: optional OpenAI Responses API provider for model-generated JSON actions.
