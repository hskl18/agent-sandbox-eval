# Examples

This directory documents reproducible example runs.
Generated trajectories and reports are intentionally written to `runs/` and `reports/`, which are ignored by git.

## Full Local Benchmark

```bash
ase run --agent react --provider local-solution --benchmark all --out runs/react-all.jsonl
ase report runs/react-all.jsonl --out reports/react-all.md
ase replay runs/react-all.jsonl --task pass-command-001
```

Expected summary:

```text
tasks=25 passed=25 pass_rate=100.0% out=runs/react-all.jsonl
```

## Agent Comparison

```bash
ase run --agent react --provider local-solution --benchmark all --out runs/react-all.jsonl
ase run --agent planner --provider local-solution --benchmark all --out runs/planner-all.jsonl
ase run --agent scripted --benchmark all --out runs/scripted-all.jsonl
ase compare runs/react-all.jsonl runs/planner-all.jsonl runs/scripted-all.jsonl --out reports/compare.md
```

The comparison report includes pass rate, average tool calls, average runtime, and top failure mode per agent.

## Failure Evidence

```bash
ase run --agent noop --benchmark terminal --task-id pass-command-001 --out runs/noop-pass-command.jsonl
ase report runs/noop-pass-command.jsonl --out reports/noop-pass-command.md
```

Expected failure mode:

```text
no_progress
```

## Repeated Local Controls

```bash
ase run-matrix examples/experiments/local-controls.yaml
ase run-matrix examples/experiments/local-controls.yaml
ase matrix-report examples/experiments/local-controls.yaml
```

The second run validates and resumes completed task trials.
It reports zero newly executed attempts when the first run completed cleanly.
The generated JSON and Markdown reports keep retries and environment-invalid trials separate from first-attempt capability metrics.
