import json
from pathlib import Path

import pytest

from agent_sandbox_eval.benchmarks.loader import load_task
from agent_sandbox_eval.model_providers.base import StepContext
from agent_sandbox_eval.model_providers.openai_responses import OpenAIResponsesProvider


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_openai_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    provider = OpenAIResponsesProvider(api_key=None)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        provider.actions(task)


def test_openai_provider_parses_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    captured = {}
    model_output = {
        "plan": ["write answer"],
        "actions": [
            {
                "kind": "tool",
                "tool": "shell",
                "input": {"cmd": "printf 'ready\\n' > answer.txt"},
                "message": "",
            },
            {"kind": "final", "tool": None, "input": {}, "message": "done"},
        ],
    }

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "id": "resp_test",
                "output_text": json.dumps(model_output),
                "usage": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setenv("OPENAI_INPUT_COST_PER_1M", "2")
    monkeypatch.setenv("OPENAI_OUTPUT_COST_PER_1M", "8")
    provider = OpenAIResponsesProvider(api_key="test-key", model="test-model", timeout_seconds=7)

    plan = provider.plan(task)
    actions = provider.actions(task)

    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["timeout"] == 7
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["text"]["format"]["type"] == "json_schema"
    assert plan == ["write answer"]
    assert actions[0].tool == "shell"
    assert actions[0].input == {"cmd": "printf 'ready\\n' > answer.txt"}
    assert actions[-1].kind == "final"
    call_records = provider.drain_call_records()
    assert len(call_records) == 1
    assert call_records[0] | {"duration_ms": 0} == {
        "provider": "openai-responses",
        "model": "test-model",
        "response_id": "resp_test",
        "duration_ms": 0,
        "input_tokens": 120,
        "output_tokens": 30,
        "total_tokens": 150,
        "estimated_cost_usd": 0.00048,
        "cost_rates_configured": True,
    }


def test_openai_provider_step_prompt_includes_observations(monkeypatch: pytest.MonkeyPatch) -> None:
    task = load_task(Path("benchmarks/terminal/pass-command-001/task.yaml"))
    captured = {}
    model_output = {
        "plan": ["finish"],
        "actions": [{"kind": "final", "tool": None, "input": {}, "message": "done"}],
    }

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"output_text": json.dumps(model_output)})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OpenAIResponsesProvider(api_key="test-key")

    action = provider.next_action(
        task,
        StepContext(
            step_index=1,
            observations=[
                {
                    "tool": "shell",
                    "input": {"cmd": "pytest -q"},
                    "stdout": "1 failed",
                    "stderr": "",
                    "exit_code": 1,
                }
            ],
        ),
    )

    assert action.kind == "final"
    prompt = captured["payload"]["input"]
    assert "Step index: 1" in prompt
    assert "1 failed" in prompt
    assert "pytest -q" in prompt
