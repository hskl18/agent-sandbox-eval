from __future__ import annotations

from agent_sandbox_eval.agents.base import AgentContext, AgentResult
from agent_sandbox_eval.model_providers.base import ModelProvider, StepContext
from agent_sandbox_eval.model_providers.local_solution import LocalSolutionProvider
from agent_sandbox_eval.model_providers.telemetry import record_provider_calls


class PlannerExecutorAgent:
    name = "planner"

    def __init__(self, provider: ModelProvider | None = None) -> None:
        self.provider = provider or LocalSolutionProvider()

    def run(self, context: AgentContext) -> AgentResult:
        try:
            plan = self.provider.plan(context.task)
        finally:
            record_provider_calls(context, self.provider, self.name)
        context.recorder.record(
            "agent_message",
            context.task.id,
            agent=self.name,
            message="Plan:\n" + "\n".join(f"{index + 1}. {step}" for index, step in enumerate(plan)),
        )

        tool_calls = 0
        observations: list[dict] = []
        for index in range(1, context.task.limits.max_tool_calls + 2):
            try:
                action = self.provider.next_action(
                    context.task,
                    StepContext(step_index=index - 1, observations=observations),
                )
            finally:
                record_provider_calls(context, self.provider, self.name)
            if action.kind == "final":
                context.recorder.record(
                    "agent_message",
                    context.task.id,
                    agent=self.name,
                    message=f"Plan complete: {action.message}",
                )
                return AgentResult(final_answer=action.message)
            if action.kind != "tool" or not action.tool:
                raise ValueError(f"unsupported action: {action}")
            if action.tool not in context.tools:
                raise ValueError(f"provider requested unavailable tool: {action.tool}")
            if tool_calls >= context.task.limits.max_tool_calls:
                return AgentResult(final_answer="Stopped after reaching max tool-call budget.")
            context.recorder.record(
                "agent_message",
                context.task.id,
                agent=self.name,
                message=f"Executing plan step {index}: {action.tool}",
            )
            result = context.tools[action.tool].run(action.input, context)
            observations.append(
                {
                    "tool": action.tool,
                    "input": action.input,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code,
                    "duration_ms": result.duration_ms,
                }
            )
            tool_calls += 1
        return AgentResult(final_answer="Provider returned no final action.")
