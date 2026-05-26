# Tool Protocol

Tools expose controlled capabilities to agents and return structured results.

Every tool should provide:

- `name`
- `description`
- `run(input, context) -> ToolResult`

`ToolResult` includes:

- `stdout`
- `stderr`
- `exit_code`
- `duration_ms`

Tools should record `tool_call` and `tool_result` trajectory events. Tools that execute code or commands should run inside the task sandbox.

External tools can be registered with Python entry points. See `docs/extensions.md`.
