# Experiment Matrices

Agent Sandbox Eval v0.2.0 adds a versioned repeated-trial experiment format and the `ase run-matrix` command.
The matrix runner executes every selected task for every cell and trial.
Each attempt has a deterministic run identifier, an independent raw trajectory, a content hash, and an atomic attempt marker.

## Experiment Schema

Experiment files use `schema_version: 1`.
The complete local-control example is [`examples/experiments/local-controls.yaml`](../examples/experiments/local-controls.yaml).

The schema records these reproducibility inputs:

- `matrix` identifies every agent, provider, model, and associated metadata.
- `benchmark` identifies a benchmark family and a versioned split.
- `trials` and `seed` define the repeated-trial protocol.
- `budgets` caps per-command time and tool calls and records validation ceilings for tokens and estimated cost.
- `environment` records a stable environment identifier, Docker image, and operator metadata.
- `retry` records the maximum attempts and the exact failure modes eligible for retry.
- `artifacts` identifies the raw trajectory directory and machine-readable and Markdown report destinations.

Relative artifact roots are resolved from the experiment file.
The matrix snapshot stores the resolved experiment specification, benchmark split, selected task definitions, task workspace content hashes, core implementation hashes, attempt executor identity, extension identities, and a fingerprint over those inputs.
An existing artifact root can only be resumed with an identical snapshot.
Workspace snapshots hash file bytes, type, size, permissions, and modification time without following symbolic links.
Task workspaces containing internal, external, broken, or cyclic symbolic links are rejected before sandbox copying or execution.
Custom attempt executor objects must implement `__ase_experiment_identity__()` and return a stable mapping containing every behavior-driving configuration value.
Executor identity mappings may contain only finite JSON scalars, string-keyed mappings, lists, and tuples.
Unknown, cyclic, or unsupported executor identity state fails closed before execution.

## Run and Resume

Run the no-cost local controls with:

```bash
ase run-matrix examples/experiments/local-controls.yaml
```

Run the same command again to resume.
Completed units are validated and skipped.
Missing raw files, changed hashes, malformed events, non-contiguous steps, changed task content, changed split content, changed implementation identity, and mismatched run identities stop the run instead of being silently regenerated.

Regenerate both reports from the validated raw artifacts with:

```bash
ase matrix-report examples/experiments/local-controls.yaml
```

Report regeneration never calls an agent or provider.
It fails closed when an attempt marker or referenced raw trajectory is missing or corrupt.
Marker outcomes, failure scopes, retry decisions, latency, token counts, and estimated cost are checked against a hashed raw `attempt_result`, grader evidence, and model-call evidence before reporting.
When execution fails after one or more model calls, valid partial raw events still contribute their recorded token usage and estimated cost while the trajectory remains marked incomplete.
ReAct and planner agents drain provider call telemetry in a `finally` path, so usage returned before output or action parsing fails is recorded exactly once.

## Reliability Metrics

Capability metrics use first attempts only.
Retries never improve pass@k or pass^k.
Retry-assisted passes have their own count.

The report uses these definitions for each task and matrix cell:

- `pass@1` is the empirical first-attempt success rate across capability-eligible trials.
- `pass@k` estimates the probability that at least one of `k` sampled trials succeeds.
- `pass^k` estimates the probability that all `k` sampled trials succeed.
- `bernoulli_variance` is `p * (1 - p)` across capability-eligible first attempts.
- `observed_first_attempt_pass_rate` keeps environment-invalid trials in the denominator.

Cell-level pass metrics are the arithmetic mean of the per-task estimates.
Environment, task, harness, and configuration failures are excluded from the capability denominator and counted separately.
Timeout and budget failures remain visible under the budget failure scope.
Task or grader failures remain visible under the task failure scope.
All remaining first-attempt failures use the capability scope.

Latency and token totals are reported for first attempts and all attempts.
Estimated cost remains unavailable unless the experiment supplies nonnegative input and output rates and a pricing source.
Provider environment variables do not silently establish experiment pricing.
Token and cost ceilings are checked after an attempt and cannot prevent a provider from charging for that attempt.

## Benchmark Splits

Versioned split files live under `benchmarks/splits/`.
List them with:

```bash
ase list-splits
```

The bundled `all` split selects every task.
The bundled `smoke` split selects one terminal, one SWE-lite, and one MCP-like task for fast end-to-end control runs.
Split files can include or exclude stable task identifiers and tags.
