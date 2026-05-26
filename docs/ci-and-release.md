# CI and Release Notes

The CI workflow in `.github/workflows/ci.yml` protects the core open-source contract:

- The package installs from a fresh checkout.
- Unit tests pass.
- Every bundled task manifest validates.
- The Docker-backed benchmark smoke test passes with the `react` agent and `local-solution` provider.
- A Markdown report can be generated from the trajectory output.

## Local Release Checklist

Before tagging a release:

```bash
python3 -m pip install -e .
python3 -m pytest -q
python3 -m mypy agent_sandbox_eval
ase validate-tasks --benchmark all
ase run --agent react --provider local-solution --benchmark all --out runs/react-all.jsonl
ase run --agent planner --provider local-solution --benchmark all --out runs/planner-all.jsonl
ase compare runs/react-all.jsonl runs/planner-all.jsonl --out reports/compare.md
```

## Compatibility

The current task manifest schema version is `1`.

The current trajectory event schema version is `1`.

Breaking changes to either schema should include migration notes and a version bump.
