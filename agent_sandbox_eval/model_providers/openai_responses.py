from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from agent_sandbox_eval.benchmarks.schema import Task
from agent_sandbox_eval.model_providers.base import AgentAction, StepContext


class OpenAIResponsesProvider:
    """OpenAI Responses API provider that asks for structured agent actions."""

    name = "openai-responses"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, dict[str, Any]] = {}
        self._step_cache: dict[tuple[str, int], AgentAction] = {}
        self._call_records: list[dict[str, Any]] = []

    def drain_call_records(self) -> list[dict[str, Any]]:
        records = list(self._call_records)
        self._call_records.clear()
        return records

    def plan(self, task: Task) -> list[str]:
        decision = self._decision(task)
        plan = decision.get("plan", [])
        if not isinstance(plan, list):
            raise ValueError("OpenAI provider response field 'plan' must be a list")
        return [str(step) for step in plan]

    def actions(self, task: Task) -> list[AgentAction]:
        decision = self._decision(task)
        raw_actions = decision.get("actions", [])
        if not isinstance(raw_actions, list):
            raise ValueError("OpenAI provider response field 'actions' must be a list")

        actions: list[AgentAction] = []
        for raw in raw_actions:
            if not isinstance(raw, dict):
                raise ValueError("OpenAI provider actions must be objects")
            kind = str(raw.get("kind", ""))
            if kind == "tool":
                tool = raw.get("tool")
                input_payload = raw.get("input", {})
                if not isinstance(tool, str) or not tool:
                    raise ValueError("tool actions require a tool name")
                if not isinstance(input_payload, dict):
                    raise ValueError("tool action input must be an object")
                actions.append(AgentAction(kind="tool", tool=tool, input=input_payload))
            elif kind == "final":
                actions.append(AgentAction(kind="final", message=str(raw.get("message", ""))))
            else:
                raise ValueError(f"unsupported OpenAI provider action kind: {kind}")
        if not any(action.kind == "final" for action in actions):
            actions.append(AgentAction(kind="final", message="No final action was provided."))
        return actions

    def next_action(self, task: Task, context: StepContext) -> AgentAction:
        key = (task.id, context.step_index)
        if key not in self._step_cache:
            decision = self._request_decision(task, context)
            raw_actions = decision.get("actions", [])
            if not isinstance(raw_actions, list) or not raw_actions:
                raise ValueError("OpenAI step response must include at least one action")
            self._step_cache[key] = _parse_action(raw_actions[0])
        return self._step_cache[key]

    def _decision(self, task: Task) -> dict[str, Any]:
        if task.id not in self._cache:
            self._cache[task.id] = self._request_decision(task, StepContext(step_index=0, observations=[]))
        return self._cache[task.id]

    def _request_decision(self, task: Task, context: StepContext) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for --provider openai-responses")

        payload = {
            "model": self.model,
            "instructions": _instructions(),
            "input": _task_prompt(task, context),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "agent_sandbox_eval_actions",
                    "strict": False,
                    "schema": _response_schema(),
                }
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI Responses API request failed: HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI Responses API request failed: {exc.reason}") from exc

        self._call_records.append(
            _call_record(
                response_data,
                provider=self.name,
                model=self.model,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
        )
        text = _extract_response_text(response_data)
        try:
            decision = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"OpenAI provider returned non-JSON output: {text[:500]}") from exc
        if not isinstance(decision, dict):
            raise ValueError("OpenAI provider output must be a JSON object")
        return decision


def _instructions() -> str:
    return (
        "You are controlling an evaluation agent. Return only structured JSON matching the schema. "
        "Choose tool actions that operate inside the sandbox. Prefer deterministic verification. "
        "Do not request tools that are not listed."
    )


def _parse_action(raw: dict[str, Any]) -> AgentAction:
    kind = str(raw.get("kind", ""))
    if kind == "tool":
        tool = raw.get("tool")
        input_payload = raw.get("input", {})
        if not isinstance(tool, str) or not tool:
            raise ValueError("tool actions require a tool name")
        if not isinstance(input_payload, dict):
            raise ValueError("tool action input must be an object")
        return AgentAction(kind="tool", tool=tool, input=input_payload)
    if kind == "final":
        return AgentAction(kind="final", message=str(raw.get("message", "")))
    raise ValueError(f"unsupported OpenAI provider action kind: {kind}")


def _task_prompt(task: Task, context: StepContext) -> str:
    allowed = task.allowed_tools or ["shell", "file_read", "file_write", "python", "mcp_state"]
    success = {
        "type": task.success.type,
        "command": task.success.command,
        "expected_exit_code": task.success.expected_exit_code,
        "path": task.success.path,
        "contains": task.success.contains,
    }
    return "\n".join(
        [
            f"Task id: {task.id}",
            f"Benchmark: {task.benchmark}",
            f"Title: {task.title}",
            f"Instruction: {task.instruction}",
            f"Allowed tools: {json.dumps(allowed)}",
            f"Success criteria: {json.dumps(success, sort_keys=True)}",
            f"Step index: {context.step_index}",
            f"Prior observations: {json.dumps(context.observations, sort_keys=True)[-6000:]}",
            "Return a concise plan and an action list. For stepwise execution, put the next action first. "
            "Tool actions must use the tool names exactly. If the observations prove the task is complete, return a final action.",
        ]
    )


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["plan", "actions"],
        "properties": {
            "plan": {
                "type": "array",
                "items": {"type": "string"},
            },
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "tool", "input", "message"],
                    "properties": {
                        "kind": {"type": "string", "enum": ["tool", "final"]},
                        "tool": {"type": ["string", "null"]},
                        "input": {"type": "object", "additionalProperties": True},
                        "message": {"type": "string"},
                    },
                },
            },
        },
    }


def _extract_response_text(response_data: dict[str, Any]) -> str:
    output_text = response_data.get("output_text")
    if isinstance(output_text, str):
        return output_text

    parts: list[str] = []
    for item in response_data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
    if parts:
        return "".join(parts)
    raise ValueError("OpenAI response did not contain output_text")


def _call_record(
    response_data: dict[str, Any],
    provider: str,
    model: str,
    duration_ms: int,
) -> dict[str, Any]:
    usage = response_data.get("usage")
    typed_usage = usage if isinstance(usage, dict) else {}
    input_tokens = int(typed_usage.get("input_tokens") or 0)
    output_tokens = int(typed_usage.get("output_tokens") or 0)
    total_tokens = int(typed_usage.get("total_tokens") or input_tokens + output_tokens)
    input_rate = _optional_nonnegative_float("OPENAI_INPUT_COST_PER_1M")
    output_rate = _optional_nonnegative_float("OPENAI_OUTPUT_COST_PER_1M")
    estimated_cost = None
    if input_rate is not None and output_rate is not None:
        estimated_cost = round(
            (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000,
            8,
        )
    return {
        "provider": provider,
        "model": model,
        "response_id": response_data.get("id"),
        "duration_ms": duration_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost,
        "cost_rates_configured": estimated_cost is not None,
    }


def _optional_nonnegative_float(name: str) -> float | None:
    value = os.environ.get(name)
    if value is None:
        return None
    parsed = float(value)
    if parsed < 0:
        raise ValueError(f"{name} must be nonnegative")
    return parsed
