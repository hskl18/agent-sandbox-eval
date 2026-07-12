# Real-model Runbook

No real-model benchmark result is checked into this repository yet.
The `openai-responses` provider has mocked unit coverage, but mocked calls do not count as agent capability evidence.

Run this protocol only after an operator supplies a test key, approves the model choices, and accepts the expected API cost.

## Fixed protocol

1. Use one repository commit and one Docker version for every configuration.
2. Run the same benchmark pack with `react` and `planner` for each model.
3. Run at least three trials per agent and model pair.
4. Keep task order, tool limits, timeout limits, sandbox image, and prompts unchanged.
5. Publish every JSONL trajectory, not only successful trials.

Capture the environment before the first run:

```bash
git rev-parse HEAD
docker version
python --version
ase validate-tasks --benchmark all
```

Configure the provider and explicit cost rates from the provider pricing source used on the run date:

```bash
export OPENAI_API_KEY=example_operator_supplied_key
export OPENAI_INPUT_COST_PER_1M=example_input_rate
export OPENAI_OUTPUT_COST_PER_1M=example_output_rate
```

The harness stores token counts, request latency, model identifier, and estimated cost in `model_call` trajectory events.
It does not store the API key, full provider response, or raw hidden reasoning.

## Run one model configuration

Set an exact model identifier instead of a floating alias when the provider offers one.

```bash
export OPENAI_MODEL=example_exact_model_id

for trial in 1 2 3; do
  ase run \
    --agent react \
    --provider openai-responses \
    --benchmark all \
    --out "runs/model-a-react-trial-${trial}.jsonl"

  ase run \
    --agent planner \
    --provider openai-responses \
    --benchmark all \
    --out "runs/model-a-planner-trial-${trial}.jsonl"
done
```

Repeat the same commands with a second approved model identifier and a separate output prefix.

## Report

Generate one report per trajectory and one comparison across all trials.

```bash
ase report runs/model-a-react-trial-1.jsonl --out reports/model-a-react-trial-1.md
ase compare runs/model-*-trial-*.jsonl --out reports/model-comparison.md
```

The published summary should include:

- pass@1 and repeated-trial pass rate by task and configuration;
- latency, model calls, input tokens, output tokens, tool calls, and estimated cost;
- timeout, invalid-action, sandbox, and task or grader failure rates;
- the deterministic failure taxonomy and representative trace evidence;
- the repository commit, task-pack commit, Python version, Docker version, and sandbox image.

Do not compare a scripted oracle or `local-solution` run with a model run as if both measure agent reasoning.
Keep oracle, deterministic harness, negative-control, and live-model sections visually separate.
