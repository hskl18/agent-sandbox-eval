# Agent Sandbox Eval Comparison

| Agent | Tasks | Pass Rate | Avg Tool Calls | Model Calls | Tokens | Est. Cost | Avg Runtime | Top Failure | Trajectory |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| scripted | 25 | 100.0% | 1.0 | 0 | 0 | $0.000000 | 973ms | none | `results/v1/scripted-oracle.jsonl` |
| react | 25 | 100.0% | 1.0 | 0 | 0 | $0.000000 | 1062ms | none | `results/v1/react-local-solution.jsonl` |
| noop | 25 | 0.0% | 0.0 | 0 | 0 | $0.000000 | 525ms | no_progress | `results/v1/noop-negative-control.jsonl` |
