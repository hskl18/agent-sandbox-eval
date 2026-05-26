from __future__ import annotations

from agent_sandbox_eval.agents.base import Agent
from agent_sandbox_eval.agents.noop import NoopAgent
from agent_sandbox_eval.agents.planner import PlannerExecutorAgent
from agent_sandbox_eval.agents.react import ReActAgent
from agent_sandbox_eval.agents.scripted import ScriptedAgent
from agent_sandbox_eval.extensions import AGENT_ENTRY_POINT_GROUP, PROVIDER_ENTRY_POINT_GROUP, load_entry_point
from agent_sandbox_eval.model_providers.local_solution import LocalSolutionProvider
from agent_sandbox_eval.model_providers.openai_responses import OpenAIResponsesProvider


def get_agent(name: str, provider_name: str = "local-solution") -> Agent:
    provider = get_provider(provider_name)
    if name == "noop":
        return NoopAgent()
    if name == "scripted":
        return ScriptedAgent()
    if name == "react":
        return ReActAgent(provider)
    if name == "planner":
        return PlannerExecutorAgent(provider)
    factory = load_entry_point(AGENT_ENTRY_POINT_GROUP, name)
    if factory is not None:
        return factory(provider=provider)
    raise ValueError(f"unknown agent: {name}")


def get_provider(name: str):
    if name == "local-solution":
        return LocalSolutionProvider()
    if name == "openai-responses":
        return OpenAIResponsesProvider()
    factory = load_entry_point(PROVIDER_ENTRY_POINT_GROUP, name)
    if factory is not None:
        return factory()
    raise ValueError(f"unknown provider: {name}")
