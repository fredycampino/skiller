from __future__ import annotations

from types import SimpleNamespace

import pytest

from skiller.domain.agent.llm_model import (
    LLMRequest,
    LLMToolCall,
    LLMToolCallFunction,
    LLMUserMessage,
)
from skiller.infrastructure.llm import openai_llm
from skiller.infrastructure.llm.openai_llm import OpenAILLM

pytestmark = pytest.mark.unit


class _FakeCompletions:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):  # noqa: ANN001
        self.calls.append(kwargs)
        return self.response


class _FakeClient:
    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        self.kwargs = kwargs
        self.completions = _FakeCompletions(
            SimpleNamespace(
                model="gpt-5.2",
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(role="assistant", content="hello", tool_calls=[]),
                    )
                ],
            )
        )
        self.chat = SimpleNamespace(completions=self.completions)


def test_openai_llm_generates_response_with_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_llm, "_load_openai_client_class", lambda: _FakeClient)

    llm = OpenAILLM(
        api_key="secret-key",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30.0,
    )

    result = llm.generate(
        LLMRequest(
            messages=(LLMUserMessage("hello"),),
            model="gpt-5.2",
        )
    )

    assert llm.client.kwargs == {
        "api_key": "secret-key",
        "base_url": "https://api.openai.com/v1",
        "timeout": 30.0,
    }
    assert llm.client.completions.calls == [
        {
            "model": "gpt-5.2",
            "messages": [{"role": "user", "content": "hello"}],
            "extra_body": {"reasoning_split": True},
        }
    ]
    assert result.ok is True
    assert result.content == "hello"
    assert result.model == "gpt-5.2"
    assert result.finish_reason == "stop"
    assert result.tool_calls == ()


def test_openai_llm_returns_error_when_api_key_missing() -> None:
    llm = OpenAILLM(
        api_key="",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30.0,
    )

    result = llm.generate(
        LLMRequest(
            messages=(LLMUserMessage("hello"),),
            model="model1",
        )
    )

    assert result.ok is False
    assert result.error == "API key is not configured for the selected model provider"
    assert result.error_code == "api_key_missing"


def test_openai_llm_maps_tool_calls_from_openai_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeToolClient:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            self.kwargs = kwargs
            self.completions = _FakeCompletions(
                SimpleNamespace(
                    model="gpt-5.2",
                    choices=[
                        SimpleNamespace(
                            finish_reason="tool_calls",
                            message=SimpleNamespace(
                                role="assistant",
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        id="call_1",
                                        function=SimpleNamespace(
                                            name="shell",
                                            arguments='{"command":"git status"}',
                                        ),
                                    )
                                ],
                            ),
                        )
                    ],
                )
            )
            self.chat = SimpleNamespace(completions=self.completions)

    monkeypatch.setattr(openai_llm, "_load_openai_client_class", lambda: _FakeToolClient)

    llm = OpenAILLM(
        api_key="secret-key",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30.0,
    )

    result = llm.generate(
        LLMRequest(
            messages=(LLMUserMessage("hello"),),
            model="gpt-5.2",
        )
    )

    assert result.ok is True
    assert result.content is None
    assert result.model == "gpt-5.2"
    assert result.finish_reason == "tool_calls"
    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command":"git status"}',
            ),
        ),
    )
