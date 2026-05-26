# Agent Sandbox Eval Proposal

## Summary

Agent Sandbox Eval is an open-source framework for evaluating tool-using AI agents in reproducible sandboxed environments. It provides a local-first CLI, Docker-based execution sandboxes, structured task definitions, trajectory recording, deterministic grading, and failure analysis reports.

The project is intended to be a real developer tool, not a demo script. Its first version should help researchers and engineers answer a practical question:

> When an agent is given tools and a real workspace, can it complete the task safely, reproducibly, and verifiably?

## Problem

Agent evaluations often stop at final-answer correctness or rely on ad hoc scripts. That is not enough for tool-using agents. Real agent behavior includes planning, command execution, file edits, environment setup, verification, retries, and failure recovery. A useful evaluation system must capture those steps and make them inspectable.

Common gaps in lightweight agent eval projects:

- Task environments are not isolated or reproducible.
- Tool calls are logged inconsistently or not at all.
- Pass/fail grading is mixed into agent code.
- Failure reasons are difficult to compare across runs.
- Benchmarks are hard to extend with new tasks.
- Reports do not expose whether the agent actually verified its work.

Agent Sandbox Eval addresses these gaps with a small, composable evaluation harness.

## Goals

- Run agent tasks in clean Docker sandboxes.
- Support multiple agent implementations through a common runner interface.
- Provide a stable tool protocol for shell, file, Python, and MCP-like tools.
- Define benchmark tasks with portable manifests.
- Record complete trajectories as structured JSONL.
- Grade tasks deterministically whenever possible.
- Classify failures with evidence.
- Generate human-readable reports for debugging and comparison.
- Make the project easy to install, run, test, and extend as open-source software.

## Non-Goals

- No web dashboard in the initial release.
- No model training or fine-tuning.
- No full SWE-bench reproduction in the MVP.
- No unrestricted arbitrary command execution outside sandbox boundaries.
- No LLM judge as the only source of correctness.
- No hosted service requirement; the core project should work locally.

## Target Users

- AI engineers building and debugging tool-using agents.
- Researchers studying agent reliability and trajectory quality.
- Developers who want a lightweight local benchmark harness.
- Open-source contributors adding tasks, tools, agents, graders, or reports.

## Product Shape

The initial product is a Python CLI package:

```bash
ase list-tasks
ase run --agent react --benchmark terminal --out runs/react-terminal.jsonl
ase report runs/react-terminal.jsonl --out reports/react-terminal.md
ase replay runs/react-terminal.jsonl --task fix-python-test-001
```

The same commands should also work through the Python module:

```bash
python -m agent_sandbox_eval run --agent react --benchmark terminal
```

The CLI should be stable enough for local use, CI jobs, and reproducible benchmark runs.

## Core Concepts

### Task

A task is a self-contained benchmark unit. It defines:

- User-facing instruction.
- Workspace files.
- Setup commands.
- Allowed tools.
- Resource limits.
- Success criteria.
- Optional metadata and tags.

Example:

```yaml
id: fix-python-test-001
benchmark: swe_lite
title: Fix a failing calculator test
instruction: >
  The package has one failing pytest test. Find the bug, patch the code,
  and verify that the test suite passes.
workspace: benchmarks/swe_lite/fix-python-test-001/workspace
setup:
  - pip install -e .
success:
  type: command
  command: pytest -q
  expected_exit_code: 0
limits:
  timeout_seconds: 120
  max_tool_calls: 30
  memory_mb: 1024
  network: false
tags:
  - python
  - debugging
  - tests
```

### Agent

An agent is an implementation that receives a task, uses tools, and returns a final result. The framework should include reference agents but not assume one model provider.

Initial agents:

- `react`: a minimal ReAct-style loop.
- `planner`: a planner-executor loop with explicit plan updates.
- `noop`: a testing agent that performs no work and is useful for harness validation.

### Tool

Tools expose controlled capabilities to agents. All tools should share one interface and produce structured results.

Initial tools:

- `shell`: run commands inside the sandbox.
- `file_read`: read files from the task workspace.
- `file_write`: write or patch files in the task workspace.
- `python`: run short Python snippets inside the sandbox.
- `mcp_state`: interact with a small local MCP-like state service.

### Sandbox

The sandbox is responsible for reproducibility and safety. Every task run should get a clean workspace and bounded execution environment.

Required behavior:

- Start from a fresh task workspace copy.
- Run setup commands inside Docker.
- Execute agent tool calls inside Docker.
- Enforce timeout, memory, CPU, and network settings.
- Capture stdout, stderr, exit code, and runtime.
- Preserve final workspace artifacts for inspection when requested.
- Remove containers after completion by default.

### Trajectory

A trajectory is the structured record of one agent attempt. It should be append-only JSONL so large runs can stream to disk.

Example event:

```json
{
  "run_id": "2026-05-26T17-30-00Z-react-terminal",
  "task_id": "fix-python-test-001",
  "step_index": 4,
  "event_type": "tool_result",
  "agent": "react",
  "tool": "shell",
  "input": {"cmd": "pytest -q"},
  "output": {
    "stdout": "1 failed, 4 passed",
    "stderr": "",
    "exit_code": 1
  },
  "duration_ms": 1204,
  "timestamp": "2026-05-26T17:31:12Z"
}
```

Required event types:

- `run_start`
- `task_start`
- `agent_message`
- `tool_call`
- `tool_result`
- `grader_result`
- `task_end`
- `run_end`

### Grader

The grader is separate from the agent. It evaluates the final sandbox state using task-defined success criteria.

Supported MVP checks:

- Command exits with expected code.
- File exists.
- File content contains or matches expected text.
- JSON output matches expected fields.
- Runtime and tool-call budget were respected.

Grader result:

```json
{
  "task_id": "fix-python-test-001",
  "passed": false,
  "score": 0.0,
  "failure_mode": "incomplete_verification",
  "evidence": [
    "Agent edited calculator.py",
    "Agent did not run the success command after the final edit",
    "Final grader command failed with exit code 1"
  ]
}
```

## Failure Taxonomy

The first release should use rule-based classification. LLM-assisted analysis can be added later, but deterministic evidence should remain visible.

Failure modes:

- `bad_planning`: plan ignores a key task requirement.
- `wrong_tool_selection`: tool choice prevents progress.
- `command_hallucination`: nonexistent command, file, flag, package, or path.
- `environment_setup_failure`: dependencies or setup failed before useful task work.
- `incomplete_verification`: agent changed state but did not verify correctly.
- `exceeded_budget`: timeout, step limit, or tool-call limit reached.
- `regression`: agent fixed one check but broke another.
- `no_progress`: agent repeated actions without meaningful workspace changes.
- `grader_or_task_bug`: task definition is ambiguous or incorrect.
- `unknown`: insufficient evidence for a confident label.

## Benchmark Plan

### Terminal Benchmark

Small tasks that exercise shell, files, logs, and scripts.

Examples:

- Locate files by content.
- Transform CSV or JSON files.
- Debug a failing shell script.
- Extract metrics from logs.
- Fix a broken config file.
- Write and run a small Python utility.

MVP target: 10 tasks.

### SWE-Lite Benchmark

Small local repositories with realistic failing tests.

Examples:

- Python package with one logic bug.
- TypeScript utility with one failing unit test.
- CLI tool with broken argument parsing.

MVP target: 3 tasks.

### MCP-Like Benchmark

Tasks that require tool-mediated state instead of only file edits.

Examples:

- Query local records through a state tool.
- Update a task status through an MCP-like interface.
- Reconcile tool state with file state.

MVP target: 3 tasks.

## Architecture

```text
agent_sandbox_eval/
  __init__.py
  cli.py
  config.py
  agents/
    base.py
    react.py
    planner.py
    noop.py
  tools/
    base.py
    shell.py
    files.py
    python.py
    mcp_state.py
  sandbox/
    docker.py
    workspace.py
    limits.py
  benchmarks/
    loader.py
    schema.py
    terminal/
    swe_lite/
    mcp_like/
  trajectories/
    schema.py
    recorder.py
    replay.py
  eval/
    grader.py
    metrics.py
    failure_analysis.py
  reports/
    markdown.py
tests/
  test_task_loader.py
  test_sandbox.py
  test_recorder.py
  test_grader.py
  test_failure_analysis.py
```

Execution flow:

```text
CLI
  -> load benchmark tasks
  -> create sandbox workspace
  -> run setup
  -> start trajectory recorder
  -> execute agent loop
  -> run grader
  -> classify failure
  -> write metrics and report
```

## Public Interfaces

### CLI

```bash
ase list-tasks [--benchmark terminal]
ase run --agent react --benchmark terminal --out runs/run.jsonl
ase run --agent planner --task-id fix-python-test-001
ase replay runs/run.jsonl --task fix-python-test-001
ase report runs/run.jsonl --out reports/run.md
ase validate-task benchmarks/terminal/fix-config-001/task.yaml
```

### Python API

```python
from agent_sandbox_eval import Runner, load_benchmark
from agent_sandbox_eval.agents import ReactAgent

tasks = load_benchmark("terminal")
runner = Runner(agent=ReactAgent(), output_path="runs/react-terminal.jsonl")
result = runner.run(tasks)
```

The Python API should remain minimal until the CLI behavior is stable.

## Metrics

Minimum report metrics:

- Total tasks.
- Pass rate.
- Average score.
- Average tool calls.
- Average runtime.
- Timeout rate.
- Failure-mode distribution.
- Tool-use distribution.
- Verification rate.
- Tasks with task or grader bugs.

Comparison table:

```text
Agent      Tasks  Pass Rate  Avg Tool Calls  Avg Runtime  Top Failure
react      16     62.5%      8.4             41.2s        incomplete_verification
planner    16     68.8%      10.1            55.8s        bad_planning
```

## Security Model

This project should be safe by default for local benchmarking, while being clear that Docker isolation is not a perfect security boundary for hostile code.

Default security decisions:

- Run tasks in Docker, not directly on the host.
- Disable network by default.
- Mount only the task workspace.
- Avoid mounting host credentials or user home directories.
- Enforce task-level timeouts.
- Enforce memory and CPU limits where supported.
- Keep command execution inside the container.
- Treat third-party benchmark tasks as untrusted.

Documentation should include a clear warning:

> Do not run untrusted tasks or agents with host mounts, credentials, or unrestricted network access.

## Open-Source Project Standards

The repo should include:

- `README.md`: installation, quickstart, concepts, and examples.
- `CONTRIBUTING.md`: how to add tasks, tools, agents, and graders.
- `LICENSE`: choose MIT or Apache-2.0 before first public release.
- `CODE_OF_CONDUCT.md`: standard contributor expectations.
- `SECURITY.md`: how to report sandbox or execution-safety issues.
- `pyproject.toml`: package metadata, dependencies, lint, formatting, tests.
- `examples/`: sample runs, trajectories, and reports.
- `docs/`: task format, tool protocol, sandbox model, grader model.

Quality gates:

- `pytest` passes locally.
- Formatting is deterministic.
- Type checking is enabled for core modules.
- Task manifests validate before execution.
- Sample benchmark run is reproducible.
- CI runs tests and validates sample tasks.

## Release Plan

### v0.1: Local Harness

Scope:

- Python package scaffold.
- CLI entrypoint.
- Task schema and loader.
- No-op agent.
- Shell and file tools.
- Docker sandbox runner.
- JSONL trajectory recorder.
- Deterministic command grader.
- 3 terminal tasks.

Acceptance:

- A user can run one benchmark end to end.
- Trajectory JSONL is written.
- Report shows pass/fail and runtime.

### v0.2: Real Agent Evaluation

Scope:

- ReAct agent.
- Planner agent.
- Python tool.
- 10 terminal tasks.
- 3 SWE-lite tasks.
- Failure taxonomy.
- Markdown report generator.

Acceptance:

- Two agents can run on the same tasks.
- Reports compare pass rate, runtime, tool calls, and failure modes.

### v0.3: Extensibility

Scope:

- MCP-like state tool.
- Task validation CLI.
- Plugin-style registration for tools and agents.
- More grader check types.
- Example CI workflow.
- Contribution docs.

Acceptance:

- A contributor can add a task without changing core runner code.
- A contributor can add a tool or agent with a documented interface.

### v1.0: Stable Local Benchmark Framework

Scope:

- Stable task manifest schema.
- Stable trajectory schema.
- Stable CLI commands.
- Backward-compatible report format.
- Security documentation.
- At least 25 bundled tasks.

Acceptance:

- The framework is usable as a local open-source benchmark harness.
- Breaking changes require migration notes.

## MVP Completion Criteria

The MVP is complete when:

- `ase run` executes at least one benchmark in Docker.
- `ase report` generates a Markdown report from JSONL trajectories.
- `ase replay` shows a readable step-by-step trajectory.
- At least 3 terminal tasks are bundled.
- At least one deterministic grader check is implemented.
- Unit tests cover task loading, trajectory recording, grading, and report generation.
- README quickstart works from a fresh clone.

## Documentation Plan

Required docs before public release:

- Quickstart.
- Task manifest reference.
- Tool protocol reference.
- Trajectory schema reference.
- Sandbox and security notes.
- How to add a benchmark task.
- How to add a new agent.
- How to interpret reports.

## Design Principles

- Local-first: users should not need a hosted service.
- Reproducible: the same task should run from a clean environment.
- Inspectable: every important agent action should be logged.
- Deterministic first: use deterministic grading before judge models.
- Extensible: tasks, tools, agents, and graders should be independently addable.
- Safe by default: no network and no broad host mounts unless explicitly enabled.
- Small core: prefer a reliable CLI and clear schemas before dashboards or platform features.

## Long-Term Opportunities

After the local framework is stable, possible extensions include:

- LLM-assisted failure analysis with evidence citations.
- OpenAI, Anthropic, local model, and custom model adapters.
- Richer SWE-lite benchmark packs.
- Task packs distributed as separate packages.
- HTML reports.
- CI integration for agent regression testing.
- Dataset export for trajectory filtering and post-training workflows.

## Success Definition

Agent Sandbox Eval succeeds if an external developer can clone the repo, install it, run a bundled benchmark, inspect a trajectory, understand why a task passed or failed, and add a new task without modifying the core framework.
