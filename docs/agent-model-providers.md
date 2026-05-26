# Agent and Model Provider Interface

Agents execute task work through tools. Model providers decide which actions the agent should take.

The agent loop is stepwise: after every tool call, the agent records an observation and passes the observation history back to the provider before asking for the next action. This supports ReAct-style think -> tool -> observe -> answer behavior.

Current agents:

- `noop`: performs no tool calls.
- `scripted`: executes task-provided solution commands and tool calls.
- `react`: runs a ReAct-style loop over provider actions.
- `planner`: records a plan, then executes provider actions step by step.

Current provider:

- `local-solution`: deterministic provider that converts `solution.commands` and `solution.tool_calls` from a task manifest into structured actions.
- `openai-responses`: optional OpenAI Responses API provider that asks a model to return structured JSON actions.

`local-solution` is not a model. It exists so the agent loop, tool dispatch, sandbox execution, grading, reports, and replay can be verified locally without API keys. External model providers should implement the `ModelProvider` protocol in `agent_sandbox_eval/model_providers/base.py`.

Providers should implement:

- `plan(task)`: planning text for planner-style agents.
- `actions(task)`: compatibility method for one-shot action lists.
- `next_action(task, step_context)`: stepwise action selection with prior observations.

External agents and providers can be registered with Python entry points. See `docs/extensions.md`.

Example:

```bash
ase run --agent react --provider local-solution --benchmark terminal
ase run --agent planner --provider local-solution --benchmark mcp_like
```

## OpenAI Responses Provider

Use `openai-responses` to run `react` or `planner` with a real model provider:

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4.1-mini
ase run --agent react --provider openai-responses --benchmark terminal --task-id pass-command-001
```

The provider calls `POST /v1/responses` and requests a JSON Schema structured output with:

- `plan`: list of plan steps.
- `actions`: list of tool or final actions.

For stepwise execution, only the first returned action is used on each provider call. Prior tool observations are included in the next prompt.

The provider is optional. Unit tests mock network calls, and the default local workflow does not require an API key.
