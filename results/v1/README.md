# Harness Baseline v1

GitHub Actions run `29192750621` generated this artifact from commit `cc1dba33048b27808b0611cb32c0d68231228fd6` on 2026-07-12.

Environment:

- Python 3.12.13.
- Docker Server 28.0.4.
- Linux x86_64 GitHub Actions runner.
- `python:3.13-slim` sandbox image.
- 25 bundled tasks from the repository at the recorded task-pack commit.

## Results

| Run | Classification | Passed | Model calls | Meaning |
| --- | --- | ---: | ---: | --- |
| `scripted` | Scripted oracle | 25/25 | 0 | Task solutions, Docker execution, grading, recording, reports, and replay worked together. |
| `react` + `local-solution` | Deterministic harness validation | 25/25 | 0 | The iterative ReAct loop executed task-provided solution metadata. |
| `noop` | Negative control | 0/25 | 0 | All 25 untouched tasks failed and were classified as `no_progress`. |

These results do not measure model reasoning or agent capability.
`liveModelResults` remains `null` in the manifest.

## Files

- `manifest.json` records scope, environment, commit, and summary metrics.
- `comparison.md` compares the three controls without mixing them with model results.
- `*.jsonl` files contain the raw trajectory events.
- Per-run Markdown files contain task outcomes and failure evidence.

The GitHub Actions workflow regenerates and uploads the same artifact shape on each pull request.
See [the real-model runbook](../../docs/model-runbook.md) for the separate protocol required before publishing a model comparison.
