# Failure Analysis

The grader returns deterministic pass/fail results, then failed runs are classified with rule-based failure analysis.

Current failure modes:

- `environment_setup_failure`: Docker or setup infrastructure failed.
- `exceeded_budget`: timeout or tool-call budget reached.
- `no_progress`: no agent tool calls were made.
- `command_hallucination`: output mentions a missing command, file, flag, package, or path.
- `incomplete_verification`: agent actions failed or did not verify the final state.
- `regression`: a verification-like command succeeded during the run, but final grading failed.
- `unknown`: reserved for cases that need stronger evidence.

Failure evidence is written into `grader_result.evidence` and rendered in Markdown reports under `Failure Evidence`.

Example:

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

The analysis is intentionally deterministic. LLM-assisted failure labeling can be added later, but it should preserve this evidence trail.

