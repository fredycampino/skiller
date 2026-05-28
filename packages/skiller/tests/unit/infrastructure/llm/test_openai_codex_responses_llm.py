from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from skiller.domain.agent.llm_model import LLMRequest, LLMUserMessage
from skiller.infrastructure.llm import openai_codex_responses_llm
from skiller.infrastructure.llm.openai_codex_credentials import OpenAICodexCredentials
from skiller.infrastructure.llm.openai_codex_responses_llm import (
    CODEX_BASE_URL,
    CODEX_ORIGINATOR,
    CODEX_USER_AGENT,
    OpenAICodexResponsesLLM,
)

pytestmark = pytest.mark.unit


class _FakeCredentialsLoader:
    def load(self, credentials_file: str) -> OpenAICodexCredentials:
        self.credentials_file = credentials_file
        return OpenAICodexCredentials(
            access_token="codex-token",
            account_id="account-1",
        )


class _FakeStream:
    def __init__(
        self,
        events: list[object],
        error_after_events: Exception | None = None,
    ) -> None:
        self.events = events
        self.error_after_events = error_after_events

    def __iter__(self) -> Any:
        if self.error_after_events is None:
            return iter(self.events)

        def iterator() -> Any:
            yield from self.events
            raise self.error_after_events

        return iterator()


class _FakeResponses:
    def __init__(
        self,
        events: list[object],
        error_after_events: Exception | None = None,
    ) -> None:
        self.events = events
        self.error_after_events = error_after_events
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _FakeStream:
        self.calls.append(kwargs)
        return _FakeStream(self.events, self.error_after_events)


class _FakeOpenAI:
    instances: list["_FakeOpenAI"] = []
    events: list[object] = []
    error_after_events: Exception | None = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.responses = _FakeResponses(
            self.events,
            self.error_after_events,
        )
        self.instances.append(self)


def test_openai_codex_responses_llm_builds_client_with_codex_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOpenAI.instances = []
    _FakeOpenAI.error_after_events = None
    loader = _FakeCredentialsLoader()
    monkeypatch.setattr(
        openai_codex_responses_llm,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )

    OpenAICodexResponsesLLM(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_loader=loader,
    )

    assert loader.credentials_file == "/tmp/openai-codex.json"
    assert _FakeOpenAI.instances[0].kwargs == {
        "api_key": "codex-token",
        "base_url": CODEX_BASE_URL,
        "timeout": 120,
        "default_headers": {
            "User-Agent": CODEX_USER_AGENT,
            "originator": CODEX_ORIGINATOR,
            "ChatGPT-Account-ID": "account-1",
        },
    }


def test_openai_codex_responses_llm_streams_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOpenAI.instances = []
    _FakeOpenAI.error_after_events = None
    _FakeOpenAI.events = [
        SimpleNamespace(type="response.output_text.delta", delta="hello"),
        SimpleNamespace(type="response.output_text.delta", delta=" codex"),
    ]
    monkeypatch.setattr(
        openai_codex_responses_llm,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )
    llm = OpenAICodexResponsesLLM(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_loader=_FakeCredentialsLoader(),
    )

    response = llm.generate(
        LLMRequest(
            messages=(LLMUserMessage("hello"),),
            model="gpt-5.4",
        )
    )

    assert response.ok is True
    assert response.content == "hello codex"
    assert _FakeOpenAI.instances[0].responses.calls == [
        {
            "model": "gpt-5.4",
            "instructions": "",
            "input": [{"role": "user", "content": "hello"}],
            "store": False,
            "stream": True,
        }
    ]


def test_openai_codex_responses_llm_reads_completed_event_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOpenAI.instances = []
    _FakeOpenAI.error_after_events = None
    _FakeOpenAI.events = [
        SimpleNamespace(type="response.output_text.delta", delta="hello"),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(
                model="gpt-5.4",
                status="completed",
                output=None,
                usage=SimpleNamespace(
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                ),
            ),
        ),
    ]
    monkeypatch.setattr(
        openai_codex_responses_llm,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )
    llm = OpenAICodexResponsesLLM(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_loader=_FakeCredentialsLoader(),
    )

    response = llm.generate(
        LLMRequest(
            messages=(LLMUserMessage("hello"),),
            model="gpt-5.4",
        )
    )

    assert response.ok is True
    assert response.usage is not None
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 5
    assert response.usage.total_tokens == 15


def test_openai_codex_responses_llm_keeps_stream_items_when_raw_stream_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool_call = SimpleNamespace(
        type="function_call",
        call_id="call-1",
        name="shell",
        arguments='{"command":"echo ok"}',
    )
    _FakeOpenAI.instances = []
    _FakeOpenAI.events = [
        SimpleNamespace(type="response.output_item.done", item=tool_call),
    ]
    _FakeOpenAI.error_after_events = TypeError("'NoneType' object is not iterable")
    monkeypatch.setattr(
        openai_codex_responses_llm,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )
    llm = OpenAICodexResponsesLLM(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_loader=_FakeCredentialsLoader(),
    )

    response = llm.generate(
        LLMRequest(
            messages=(LLMUserMessage("hello"),),
            model="gpt-5.4",
        )
    )

    assert response.ok is True
    assert response.model == "gpt-5.4"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].id == "call-1"
    assert response.tool_calls[0].function.name == "shell"
    assert response.tool_calls[0].function.arguments_json == '{"command":"echo ok"}'
