from __future__ import annotations

from typing import Any

from agent_sandbox_eval.agents.base import AgentContext


def record_provider_calls(context: AgentContext, provider: object, agent_name: str) -> None:
    drain = getattr(provider, "drain_call_records", None)
    if not callable(drain):
        return
    records: list[dict[str, Any]] = drain()
    for record in records:
        context.recorder.record(
            "model_call",
            context.task.id,
            agent=agent_name,
            **record,
        )
