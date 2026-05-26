from __future__ import annotations

from agent_sandbox_eval.agents.base import AgentContext, AgentResult


class NoopAgent:
    name = "noop"

    def run(self, context: AgentContext) -> AgentResult:
        context.recorder.record(
            "agent_message",
            context.task.id,
            agent=self.name,
            message="NoopAgent intentionally performed no tool calls.",
        )
        return AgentResult(final_answer="No changes made.")

