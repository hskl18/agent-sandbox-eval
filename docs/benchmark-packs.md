# Benchmark Packs

The bundled benchmark set currently contains 25 tasks.

## Terminal

Target: shell, file, log, JSON, CSV, and small Python utility tasks.

Current count: 16.

## SWE-Lite

Target: small local repositories with deterministic test or command success checks.

Current count: 6.

## MCP-Like

Target: tasks that require a stateful tool instead of only shell commands.

Current count: 3.

The `scripted` agent should pass all bundled tasks.
If it does not, the task manifest, solution, sandbox, or grader likely has a bug.

Additional benchmark packs can be distributed as Python packages through the `agent_sandbox_eval.task_packs` entry point group.
See `docs/extensions.md`.

## Versioned Splits

Benchmark splits live under `benchmarks/splits/` and use schema version `1`.
The `all` split selects the full benchmark set.
The `smoke` split selects one task from each bundled benchmark family.

List available splits with:

```bash
ase list-splits
```

Experiment matrices record both the benchmark family and split identifier.
