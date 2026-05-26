# Task Format

Tasks are defined by `task.yaml` files under `benchmarks/<benchmark>/<task-id>/`.

Required fields:

- `schema_version`: manifest schema version. Current value: `1`.
- `id`: stable task id.
- `benchmark`: benchmark family.
- `title`: short human-readable title.
- `instruction`: prompt shown to the agent.
- `workspace`: path to the task workspace, relative to the manifest.
- `success`: deterministic success criteria.

Supported MVP success criteria:

```yaml
success:
  type: command
  command: pytest -q
  expected_exit_code: 0
```

```yaml
success:
  type: file_exists
  path: answer.txt
```

```yaml
success:
  type: file_contains
  path: answer.txt
  contains: ready
```

Optional fields:

- `setup`: commands run before the agent starts.
- `allowed_tools`: tool names expected for the task.
- `limits`: timeout, memory, CPU, network, and max tool-call settings.
- `tags`: search and reporting tags.
- `solution.commands`: commands used by the `scripted` validation agent.
- `solution.tool_calls`: tool calls used by the `scripted` validation agent.

Example scripted tool calls:

```yaml
solution:
  tool_calls:
    - tool: mcp_state
      input:
        action: set
        key: status
        value: done
```

Validate all bundled tasks with:

```bash
ase validate-tasks --benchmark all
```
