# CI and Release Notes

The CI workflow in `.github/workflows/ci.yml` protects the core open-source contract:

- The package installs from a fresh checkout.
- Unit tests pass.
- Static type checks pass.
- Every bundled task manifest validates.
- Task-authoring lint passes.
- The scripted oracle, ReAct local-solution harness control, and noop negative control run in Docker.
- The versioned local-control matrix runs and emits validated JSON and Markdown reports.

## Local Release Checklist

Before tagging a release:

```bash
python3 -m pip install -e .
python3 -m pytest -q
python3 -m mypy agent_sandbox_eval
ase validate-tasks --benchmark all
ase lint-tasks --benchmark all --probe-setup
ase run --agent react --provider local-solution --benchmark all --out runs/react-all.jsonl
ase run --agent planner --provider local-solution --benchmark all --out runs/planner-all.jsonl
ase compare runs/react-all.jsonl runs/planner-all.jsonl --out reports/compare.md
ase run-matrix examples/experiments/local-controls.yaml
ase matrix-report examples/experiments/local-controls.yaml
```

## Compatibility

The current task manifest schema version is `1`.

The current trajectory event schema version is `1`.

The current experiment schema version is `1`.

The current benchmark split schema version is `1`.

The detailed pre-tag gate is in [`v0.2.0-release-checklist.md`](v0.2.0-release-checklist.md).

Breaking changes to any schema should include migration notes and a version bump.
