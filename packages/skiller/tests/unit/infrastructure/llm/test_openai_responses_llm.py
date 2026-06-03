from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from skiller.domain.agent.agent_llm_generation_model import LLMToolChoiceMode
from skiller.domain.agent.agent_llm_provider_model import AgentMiniMaxLLMModel
from skiller.domain.agent.llm_model import LLMUserMessage
from skiller.domain.agent.llm_request import MiniMaxLLMRequest
from skiller.infrastructure.llm import openai_responses_llm
from skiller.infrastructure.llm.openai_responses_llm import OpenAIResponsesLLM

pytestmark = pytest.mark.unit


class _FakeStream:
    def __init__(self, events: list[object], response: object) -> None:
        self.events = events
        self.response = response

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *args: object) -> None:
        _ = args

    def __iter__(self) -> Any:
        return iter(self.events)

    def get_final_response(self) -> object:
        return self.response


class _FakeResponses:
    def __init__(self, events: list[object], response: object) -> None:
        self.events = events
        self.response = response
        self.calls: list[dict[str, object]] = []

    def stream(self, **kwargs: object) -> _FakeStream:
        self.calls.append(kwargs)
        return _FakeStream(self.events, self.response)


class _FakeOpenAI:
    instances: list["_FakeOpenAI"] = []
    events: list[object] = []
    response: object = SimpleNamespace(
        model="gpt-5.4",
        status="completed",
        output=[],
    )

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.responses = _FakeResponses(self.events, self.response)
        self.instances.append(self)


class _FailingResponses:
    def stream(self, **kwargs: object) -> _FakeStream:
        _ = kwargs
        raise RuntimeError("boom")


class _FailingOpenAI:
    def __init__(self, **kwargs: object) -> None:
        _ = kwargs
        self.responses = _FailingResponses()


def test_openai_responses_llm_builds_client_with_responses_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOpenAI.instances = []
    monkeypatch.setattr(openai_responses_llm, "_load_openai_client_class", lambda: _FakeOpenAI)

    OpenAIResponsesLLM(
        api_key="token",
        base_url="https://chatgpt.com/backend-api/codex/",
        timeout_seconds=30,
        default_headers={"ChatGPT-Account-ID": "account"},
    )

    assert _FakeOpenAI.instances[0].kwargs == {
        "api_key": "token",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "timeout": 30,
        "default_headers": {"ChatGPT-Account-ID": "account"},
    }


def test_generate_streams_response_and_maps_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeOpenAI.instances = []
    _FakeOpenAI.events = [
        SimpleNamespace(type="response.output_text.delta", delta="hello"),
        SimpleNamespace(type="response.output_text.delta", delta=" world"),
    ]
    _FakeOpenAI.response = SimpleNamespace(
        model="gpt-5.4",
        status="completed",
        output=[],
    )
    monkeypatch.setattr(openai_responses_llm, "_load_openai_client_class", lambda: _FakeOpenAI)
    llm = OpenAIResponsesLLM(
        api_key="token",
        base_url="https://chatgpt.com/backend-api/codex",
        timeout_seconds=30,
    )

    result = llm.generate(
        MiniMaxLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentMiniMaxLLMModel.M2_7,
            tool_choice=LLMToolChoiceMode.AUTO,
            temperature=1,
            max_tokens=4096,
            top_p=1,
            parallel_tool_calls=True,
        )
    )

    assert result.ok is True
    assert result.content == "hello world"
    assert _FakeOpenAI.instances[0].responses.calls == [
        {
            "model": "MiniMax-M2.7",
            "instructions": "",
            "input": [{"role": "user", "content": "hello"}],
            "store": False,
            "tool_choice": "auto",
            "temperature": 1,
            "max_output_tokens": 4096,
            "top_p": 1,
            "parallel_tool_calls": True,
        }
    ]


def test_generate_returns_api_key_error_without_building_client() -> None:
    llm = OpenAIResponsesLLM(
        api_key=" ",
        base_url="https://chatgpt.com/backend-api/codex",
        timeout_seconds=30,
    )

    result = llm.generate(
        MiniMaxLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentMiniMaxLLMModel.M2_7,
            tool_choice=LLMToolChoiceMode.AUTO,
            temperature=1,
            max_tokens=4096,
            top_p=1,
            parallel_tool_calls=True,
        )
    )

    assert result.ok is False
    assert result.error_code == "api_key_missing"


def test_generate_returns_stream_error_event(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeOpenAI.instances = []
    _FakeOpenAI.events = [SimpleNamespace(type="error")]
    _FakeOpenAI.response = SimpleNamespace(model="gpt-5.4", status="completed", output=[])
    monkeypatch.setattr(openai_responses_llm, "_load_openai_client_class", lambda: _FakeOpenAI)
    llm = OpenAIResponsesLLM(
        api_key="token",
        base_url="https://chatgpt.com/backend-api/codex",
        timeout_seconds=30,
    )

    result = llm.generate(
        MiniMaxLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentMiniMaxLLMModel.M2_7,
            tool_choice=LLMToolChoiceMode.AUTO,
            temperature=1,
            max_tokens=4096,
            top_p=1,
            parallel_tool_calls=True,
        )
    )

    assert result.ok is False
    assert result.error_code == "stream_error"


def test_generate_returns_request_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_responses_llm, "_load_openai_client_class", lambda: _FailingOpenAI)
    llm = OpenAIResponsesLLM(
        api_key="token",
        base_url="https://chatgpt.com/backend-api/codex",
        timeout_seconds=30,
    )

    result = llm.generate(
        MiniMaxLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentMiniMaxLLMModel.M2_7,
            tool_choice=LLMToolChoiceMode.AUTO,
            temperature=1,
            max_tokens=4096,
            top_p=1,
            parallel_tool_calls=True,
        )
    )

    assert result.ok is False
    assert result.error_code == "request_failed"
    assert result.error == "OpenAI Responses request failed: boom"
