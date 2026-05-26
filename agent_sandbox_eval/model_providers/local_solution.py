from __future__ import annotations

from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.model_providers.base import AgentAction, StepContext


class LocalSolutionProvider:
    """Deterministic provider for validating agent loops without an LLM API key."""

    name = "local-solution"

    def plan(self, task: Task) -> list[str]:
        steps: list[str] = []
        if task.setup:
            steps.append("Use the prepared task environment.")
        for command in task.solution_commands:
            steps.append(f"Run shell command: {command}")
        for call in task.solution_tool_calls:
            steps.append(f"Call tool {call.get('tool')}: {call.get('input')}")
        if not steps:
            steps.append("No solution actions are available for this task.")
        steps.append("Return a final answer after tool execution.")
        return steps

    def actions(self, task: Task) -> list[AgentAction]:
        actions: list[AgentAction] = []
        for command in task.solution_commands:
            actions.append(AgentAction(kind="tool", tool="shell", input={"cmd": command}))
        for call in task.solution_tool_calls:
            tool_name = str(call.get("tool", ""))
            input_payload = call.get("input", {})
            if isinstance(input_payload, dict):
                actions.append(AgentAction(kind="tool", tool=tool_name, input=input_payload))
        actions.append(AgentAction(kind="final", message="Completed local solution actions."))
        return actions

    def next_action(self, task: Task, context: StepContext) -> AgentAction:
        actions = self.actions(task)
        if context.step_index < len(actions):
            return actions[context.step_index]
        return AgentAction(kind="final", message="No more local solution actions.")
