# Failure Analysis

The deterministic grader produces pass or fail evidence before the failure classifier assigns a category.
The classifier never uses a model and never replaces the raw tool or grader output.

## Current taxonomy

| Failure mode | Evidence signal |
| --- | --- |
| `environment_setup_failure` | Docker or task setup failed before useful work |
| `timeout` | A tool or grader command returned timeout exit code 124 |
| `exceeded_budget` | The agent reached its tool-call limit |
| `no_progress` | The agent made no tool calls |
| `planning_error` | Recorded output identifies a missing or invalid plan decision |
| `tool_selection_error` | The agent selected a disallowed or explicitly wrong tool |
| `argument_error` | A tool rejected a flag or argument |
| `environment_assumption` | Recorded output identifies an unavailable assumed dependency or condition |
| `command_hallucination` | A command, file, flag, package, or path was not found |
| `state_corruption` | Tool or grader evidence identifies invalid persisted state or JSON |
| `unsafe_action` | A sandbox or policy layer blocked an unsafe action |
| `incomplete_verification` | Tool actions failed or the agent never verified final state |
| `regression` | A verification-like command ran, but the final grader failed |
| `grader_or_task_bug` | Evidence identifies a grader mismatch or task defect |
| `unknown` | The available deterministic evidence does not support a stronger category |

Some categories require an explicit marker from a tool, policy layer, or grader.
The classifier does not infer a planning or safety failure from a generic nonzero exit code.

Failure evidence is written into `grader_result.evidence` and rendered under `Failure Evidence` in Markdown reports.

```text
## Failure Evidence

### `pass-command-001`
- Success command: test -f answer.txt && grep -q ready answer.txt
- Expected exit code: 0
- Actual exit code: 1
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.
```

The versioned negative-control baseline uses the `noop` agent to exercise `no_progress` across the bundled task pack.
Future model runs should preserve these deterministic categories and may add a separate model-assisted explanation without overwriting them.
