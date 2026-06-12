from __future__ import annotations

import pytest

from skiller.domain.agent.agent_llm_provider_model import AgentBedrockLLMModel
from skiller.domain.agent.llm_model import LLMToolCall, LLMToolCallFunction, LLMUserMessage
from skiller.domain.agent.llm_request import BedrockLLMRequest
from skiller.infrastructure.llm.bedrock import bedrock_llm_port
from skiller.infrastructure.llm.bedrock.bedrock_llm_port import BedrockLLMPort

pytestmark = pytest.mark.unit


class _FakeBedrockClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def converse(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return self.response


class _FakeSession:
    response: dict[str, object] = {}
    instances: list["_FakeSession"] = []

    def __init__(self, *, profile_name: str) -> None:
        self.profile_name = profile_name
        self.client_calls: list[dict[str, object]] = []
        self.runtime_client = _FakeBedrockClient(self.response)
        self.instances.append(self)

    def client(self, service_name: str, **kwargs: object) -> _FakeBedrockClient:
        self.client_calls.append({"service_name": service_name, **kwargs})
        return self.runtime_client


class _FakeConfig:
    def __init__(self, *, read_timeout: float) -> None:
        self.read_timeout = read_timeout


def test_bedrock_llm_port_generates_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSession.instances = []
    _FakeSession.response = {
        "stopReason": "end_turn",
        "output": {"message": {"content": [{"text": "OK"}]}},
        "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
    }
    monkeypatch.setattr(bedrock_llm_port, "_load_boto3_session_class", lambda: _FakeSession)
    monkeypatch.setattr(bedrock_llm_port, "_load_botocore_config_class", lambda: _FakeConfig)
    llm = BedrockLLMPort(
        profile="claude-bedrock",
        timeout_seconds=45,
    )

    response = llm.generate(
        BedrockLLMRequest(
            messages=(LLMUserMessage("Hola mundo"),),
            model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
        )
    )

    assert _FakeSession.instances[0].profile_name == "claude-bedrock"
    assert len(_FakeSession.instances[0].client_calls) == 1
    client_call = _FakeSession.instances[0].client_calls[0]
    assert client_call["service_name"] == "bedrock-runtime"
    config = client_call["config"]
    assert isinstance(config, _FakeConfig)
    assert config.read_timeout == 45
    assert _FakeSession.instances[0].runtime_client.calls == [
        {
            "modelId": "us.anthropic.claude-opus-4-6-v1",
            "messages": [{"role": "user", "content": [{"text": "Hola mundo"}]}],
            "inferenceConfig": {"maxTokens": 256, "temperature": 0.0},
        }
    ]
    assert response.ok is True
    assert response.content == "OK"
    assert response.finish_reason == "end_turn"
    assert response.usage is not None
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 5
    assert response.usage.total_tokens == 15


def test_bedrock_llm_port_maps_tool_use_to_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeSession.instances = []
    _FakeSession.response = {
        "stopReason": "tool_use",
        "output": {
            "message": {
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tool-1",
                            "name": "shell",
                            "input": {"command": "pwd"},
                        }
                    }
                ]
            }
        },
    }
    monkeypatch.setattr(bedrock_llm_port, "_load_boto3_session_class", lambda: _FakeSession)
    monkeypatch.setattr(bedrock_llm_port, "_load_botocore_config_class", lambda: _FakeConfig)
    llm = BedrockLLMPort(
        profile="claude-bedrock",
        timeout_seconds=45,
    )

    response = llm.generate(
        BedrockLLMRequest(
            messages=(LLMUserMessage("run"),),
            model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
        )
    )

    assert response.ok is True
    assert response.content is None
    assert response.tool_calls == (
        LLMToolCall(
            id="tool-1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command":"pwd"}',
            ),
        ),
    )


def test_bedrock_llm_port_returns_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenClient:
        def converse(self, **kwargs: object) -> dict[str, object]:
            _ = kwargs
            raise RuntimeError("boom")

    class _BrokenSession:
        def __init__(self, *, profile_name: str) -> None:
            _ = profile_name

        def client(self, service_name: str, **kwargs: object) -> _BrokenClient:
            _ = service_name
            _ = kwargs
            return _BrokenClient()

    monkeypatch.setattr(
        bedrock_llm_port,
        "_load_boto3_session_class",
        lambda: _BrokenSession,
    )
    monkeypatch.setattr(bedrock_llm_port, "_load_botocore_config_class", lambda: _FakeConfig)
    llm = BedrockLLMPort(
        profile="claude-bedrock",
        timeout_seconds=45,
    )

    response = llm.generate(
        BedrockLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
        )
    )

    assert response.ok is False
    assert response.error == "Bedrock request failed: boom"
    assert response.error_code == "request_failed"
