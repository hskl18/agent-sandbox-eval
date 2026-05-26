# Extensions

Agent Sandbox Eval supports lightweight plugin-style registration with Python package entry points.

Entry point groups:

- `agent_sandbox_eval.agents`
- `agent_sandbox_eval.providers`
- `agent_sandbox_eval.tools`
- `agent_sandbox_eval.task_packs`

## Agent Extensions

Agent entry points should load a callable factory:

```python
def make_agent(provider):
    return MyAgent(provider)
```

The returned object must implement the `Agent` protocol.

## Provider Extensions

Provider entry points should load a callable factory:

```python
def make_provider():
    return MyProvider()
```

The returned object must implement `plan(task)`, `actions(task)`, and `next_action(task, step_context)`.

## Tool Extensions

Tool entry points should load a callable factory:

```python
def make_tool(sandbox):
    return MyTool(sandbox)
```

The returned object must expose `name`, `description`, and `run(input, context)`.

## Example `pyproject.toml`

```toml
[project.entry-points."agent_sandbox_eval.task_packs"]
my-tasks = "my_package.tasks:get_benchmark_roots"

[project.entry-points."agent_sandbox_eval.providers"]
my-provider = "my_package.providers:make_provider"

[project.entry-points."agent_sandbox_eval.agents"]
my-agent = "my_package.agents:make_agent"

[project.entry-points."agent_sandbox_eval.tools"]
my-tool = "my_package.tools:make_tool"
```

List installed extensions:

```bash
ase list-extensions
```

Use an extension provider or agent:

```bash
ase run --agent my-agent --provider my-provider --benchmark terminal
```

## Task Pack Extensions

Task-pack entry points should return a path or list of paths containing benchmark directories:

```python
from importlib import resources


def get_benchmark_roots():
    return resources.files("my_package") / "benchmarks"
```

Each returned root is scanned like the built-in `benchmarks/` directory. For example, a task at:

```text
my_package/benchmarks/terminal/example-task/task.yaml
```

is discoverable with:

```bash
ase list-tasks --benchmark terminal
ase run --agent react --benchmark terminal --task-id example-task
```
