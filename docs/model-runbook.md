# Real-model Runbook

No real-model benchmark result is checked into this repository yet.
The `openai-responses` provider has mocked unit coverage, but mocked calls do not count as agent capability evidence.

Run this protocol only after an operator supplies a test key, approves the exact model identifiers, and accepts the expected API cost.

## Fixed Protocol

1. Use one repository commit and one Docker environment identity for every configuration.
2. Run the same benchmark split with ReAct and planner cells for each model.
3. Run at least three trials per agent and model pair.
4. Keep task order, seeds, budgets, sandbox image, prompts, and retry policy unchanged.
5. Publish every attempt marker and referenced JSONL trajectory.
6. Keep retries limited to explicitly named environment failures.
7. Keep first-attempt capability metrics separate from retry-assisted outcomes.

Capture the environment before the first run:

```bash
git rev-parse HEAD
docker version
python --version
ase --version
ase validate-tasks --benchmark all
ase lint-tasks --benchmark all --probe-setup
```

## Configure the Experiment

Create an operator-owned experiment YAML from [`examples/experiments/local-controls.yaml`](../examples/experiments/local-controls.yaml).
Do not commit API keys or credentials.

Set these fields for a live run:

- Set `benchmark.name` and `benchmark.split` to the approved task set.
- Set `trials` to at least `3`.
- Set every model `name` to an exact provider model identifier rather than a floating alias.
- Set each model `provider` to `openai-responses`.
- Record the provider name, model release, run date, and relevant API settings in model metadata.
- Add a `pricing` mapping with nonnegative input and output rates and the exact pricing source.
- Set token and cost budgets approved by the operator.
- Set retries to environment-only failure modes.

Pricing must be explicit in the experiment file:

```yaml
pricing:
  source: https://provider.example/pricing-observed-on-YYYY-MM-DD
  input_per_million_usd: 0.0
  output_per_million_usd: 0.0
```

Replace the example rates and source with the approved provider values.
Do not publish estimated cost when the pricing source is missing.
Token and cost ceilings are post-attempt validation checks rather than preauthorization controls.
The operator must approve the maximum possible provider spend before starting the matrix.

## Run

Export only the operator-supplied credential:

```bash
export OPENAI_API_KEY=operator_supplied_value
ase run-matrix path/to/operator-experiment.yaml
```

The matrix runner stores token counts, request latency, provider, model, trial seed, retry accounting, and estimated cost in experiment artifacts.
It does not store the API key, full provider response, or raw hidden reasoning.

Run the same command after an interruption.
Completed units resume only after their attempt markers, hashes, and raw event streams validate.
The snapshot also requires the same resolved task content, split definition, core implementation, attempt executor, and installed extension identities.
Corrupt, missing, or semantically inconsistent raw evidence stops the run.

## Report

Regenerate the machine-readable and Markdown reports from raw artifacts with:

```bash
ase matrix-report path/to/operator-experiment.yaml
```

The published summary must include:

- pass@1, pass@k, pass^k, and per-task Bernoulli variance;
- observed first-attempt pass rate and the capability-eligible denominator;
- retry attempts, retry-assisted passes, and eventual passes;
- environment, budget, task, and capability failure distributions;
- latency, input tokens, output tokens, and estimated cost with its pricing source;
- repository commit, task split, Docker image, environment identity, and experiment fingerprint;
- every raw trajectory and attempt marker needed to regenerate the summary.

Do not compare a scripted oracle or local-solution run with a model run as if both measure agent reasoning.
Keep oracle, deterministic harness, negative-control, and live-model sections visually separate.
