# Agent Sandbox Eval

Agent Sandbox Eval is a local-first framework for evaluating tool-using AI agents in reproducible Docker sandboxes.
It provides task manifests, sandboxed execution, JSONL trajectory recording, deterministic grading, repeated-trial experiment matrices, replay, and machine-readable and Markdown reports.

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
ase run-matrix examples/experiments/local-controls.yaml
```

The default provider for `react` and `planner` is `local-solution`, a deterministic provider that converts bundled solution metadata into tool actions.
It validates the loop and harness; it does not measure agent reasoning.

## Evidence Status

The repository publishes three clearly separated harness baselines:

- `scripted` is an oracle that executes task-provided validation solutions.
- `react` with `local-solution` validates iterative tool dispatch using the same task-provided metadata.
- `noop` is a negative control for grading and failure classification.

None of these is a model capability result.
No real-model leaderboard is currently published.
See the [real-model runbook](docs/model-runbook.md) for the fixed repeated-trial protocol and the metrics that must be present before a model result can be added.

The [versioned v1 harness artifact](results/v1/README.md) records:

| Control | Result | Interpretation |
| --- | ---: | --- |
| Scripted oracle | 25/25 | Bundled solutions and the end-to-end harness passed in Docker. |
| ReAct + `local-solution` | 25/25 | The iterative loop passed using task-provided solution metadata. |
| `noop` negative control | 0/25 | Untouched tasks failed, with all 25 classified as `no_progress`. |

The artifact contains 0 model calls and `liveModelResults: null`.

## Development

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m mypy agent_sandbox_eval
ase validate-tasks --benchmark all
```

Docker is required for `ase run`.
Sandbox commands run with a read-only container root, dropped Linux capabilities, `no-new-privileges`, Docker's built-in seccomp profile, a PID limit, and explicit writable workspace and temporary mounts.
These controls are defense in depth, not a guarantee that Docker safely contains every hostile workload.
See [docs/sandbox-model.md](docs/sandbox-model.md) and [SECURITY.md](SECURITY.md) for the exact boundary and limitations.

## Bundled Benchmarks

The current repository includes:

- 16 terminal tasks.
- 6 SWE-lite tasks.
- 3 MCP-like state-tool tasks.

The `scripted` agent is expected to pass every bundled task.
This validates task manifests, sandbox execution, trajectory recording, grading, reports, and replay without depending on a model provider.

Failure reports include deterministic failure modes and evidence.
See [docs/failure-analysis.md](docs/failure-analysis.md).

GitHub Actions runs the oracle, deterministic harness, and negative control against all 25 bundled tasks in Docker.
It uploads the JSONL trajectories, Markdown reports, comparison, and environment manifest as the `harness-baseline-v1` workflow artifact.

Agents, model providers, tools, and benchmark task packs can be extended through Python entry points.
See [docs/extensions.md](docs/extensions.md).

Research-backed optimization notes and the next reliability work are tracked in [docs/research-and-optimization.md](docs/research-and-optimization.md).

The [experiment matrix guide](docs/experiment-matrices.md) documents versioned schemas, benchmark splits, deterministic run identifiers, resume validation, retry accounting, pass@k, pass^k, and pricing-source requirements.

The [v0.2.0 release checklist](docs/v0.2.0-release-checklist.md) records the local and CI proof required before a maintainer creates a tag.

Reproducible example commands are listed in [examples/README.md](examples/README.md).

## Current Agent Status

- `scripted`: executes task-provided validation solutions directly.
- `noop`: performs no tool calls and is useful for negative harness tests.
- `react`: runs a ReAct-style tool loop over provider actions.
- `planner`: records a plan, then executes provider actions step by step.
- `local-solution`: deterministic provider for local validation without API keys.
- `openai-responses`: optional OpenAI Responses API provider for model-generated JSON actions.
