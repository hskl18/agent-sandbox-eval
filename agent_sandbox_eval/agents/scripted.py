from __future__ import annotations

from agent_sandbox_eval.agents.base import AgentContext, AgentResult


class ScriptedAgent:
    """Harness-validation agent that executes solution commands bundled with a task."""

    name = "scripted"

    def run(self, context: AgentContext) -> AgentResult:
        shell = context.tools["shell"]
        if not context.task.solution_commands and not context.task.solution_tool_calls:
            context.recorder.record(
                "agent_message",
                context.task.id,
                agent=self.name,
                message="Task has no solution.commands entries.",
            )
            return AgentResult(final_answer="No scripted solution available.")

        for command in context.task.solution_commands:
            shell.run({"cmd": command}, context)
        for call in context.task.solution_tool_calls:
            tool_name = str(call.get("tool", ""))
            input_payload = call.get("input", {})
            if tool_name not in context.tools:
                raise ValueError(f"scripted solution references unavailable tool: {tool_name}")
            if not isinstance(input_payload, dict):
                raise ValueError(f"scripted tool call input must be a mapping: {tool_name}")
            context.tools[tool_name].run(input_payload, context)
        return AgentResult(final_answer="Executed scripted solution commands.")
