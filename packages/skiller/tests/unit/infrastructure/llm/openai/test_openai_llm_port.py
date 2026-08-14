from __future__ import annotations

from types import SimpleNamespace

import pytest

from skiller.domain.agent.llm.model import LLMToolChoiceMode, LLMUserMessage
from skiller.domain.agent.llm.provider_minimax import MiniMaxLLMRequest
from skiller.domain.agent.llm.provider_registry import AgentMiniMaxLLMModel
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper
from skiller.infrastructure.llm.openai import openai_llm_port
from skiller.infrastructure.llm.openai.openai_llm_port import OpenAILLMPort
from skiller.infrastructure.llm.openai.openai_mapper import OpenAIMapper

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
                model="gpt-5.4",
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(role="assistant", content="hello", tool_calls=[]),
                    )
                ],
            )
        )
        self.chat = SimpleNamespace(completions=self.completions)


class _FakeRequestLogger:
    def __init__(self) -> None:
        self.requests: list[object] = []
        self.responses: list[object] = []
        self.errors: list[str] = []

    def log_request(
        self,
        *,
        request: object,
        file: object,
        overwrite: bool,
    ) -> None:
        _ = (file, overwrite)
        self.requests.append(request)

    def log_response(
        self,
        *,
        response: object,
    ) -> None:
        self.responses.append(response)

    def log_error(
        self,
        *,
        error: str,
    ) -> None:
        self.errors.append(error)


def _minimax_request(*, log_request_file: str | None = None) -> MiniMaxLLMRequest:
    return MiniMaxLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=AgentMiniMaxLLMModel.M2_7,
        tool_choice=LLMToolChoiceMode.AUTO,
        temperature=1,
        max_tokens=4096,
        top_p=1,
        parallel_tool_calls=True,
        log_request_file=log_request_file,
    )


def _expected_openai_kwargs(*, reasoning_split: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": "MiniMax-M2.7",
        "messages": [{"role": "user", "content": "hello"}],
        "tool_choice": "auto",
        "temperature": 1,
        "max_tokens": 4096,
        "top_p": 1,
        "parallel_tool_calls": True,
    }
    if reasoning_split:
        payload["extra_body"] = {"reasoning_split": True}
    return payload


def test_openai_llm_generates_response_with_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_llm_port, "_load_openai_client_class", lambda: _FakeClient)
    logger = _FakeRequestLogger()

    llm = OpenAILLMPort(
        api_key="secret-key",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30.0,
        mapper=OpenAIMapper(
            usage_mapper=DefaultLLMUsageMapper(),
            extra_body={"reasoning_split": True},
        ),
        request_logger=logger,
    )

    result = llm.generate(_minimax_request())

    assert llm.client.kwargs == {
        "api_key": "secret-key",
        "base_url": "https://api.openai.com/v1",
        "timeout": 30.0,
    }
    assert llm.client.completions.calls == [_expected_openai_kwargs(reasoning_split=True)]
    assert result.ok is True
    assert result.content == "hello"
    assert result.model == AgentMiniMaxLLMModel.M2_7
    assert result.finish_reason == "stop"
    assert result.tool_calls == ()
    assert logger.requests == []
    assert logger.responses == []
    assert logger.errors == []


def test_openai_llm_returns_error_when_api_key_missing() -> None:
    logger = _FakeRequestLogger()
    llm = OpenAILLMPort(
        api_key="",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30.0,
        mapper=OpenAIMapper(usage_mapper=DefaultLLMUsageMapper()),
        request_logger=logger,
    )

    result = llm.generate(_minimax_request())

    assert result.ok is False
    assert result.error == "API key is not configured for the selected model provider"
    assert result.error_code == "api_key_missing"
    assert logger.requests == []
    assert logger.responses == []
    assert logger.errors == []


def test_openai_llm_logs_request_and_response_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(openai_llm_port, "_load_openai_client_class", lambda: _FakeClient)
    logger = _FakeRequestLogger()

    llm = OpenAILLMPort(
        api_key="secret-key",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30.0,
        mapper=OpenAIMapper(usage_mapper=DefaultLLMUsageMapper()),
        request_logger=logger,
    )

    result = llm.generate(_minimax_request(log_request_file="/tmp/skiller-llm.json"))

    assert result.ok is True
    assert logger.requests == [_expected_openai_kwargs()]
    assert logger.responses == [llm.client.completions.response]
    assert logger.errors == []


def test_openai_llm_logs_error_when_request_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingCompletions:
        def create(self, **kwargs):  # noqa: ANN001
            _ = kwargs
            raise RuntimeError("network down")

    class _FailingClient:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            _ = kwargs
            self.chat = SimpleNamespace(completions=_FailingCompletions())

    monkeypatch.setattr(openai_llm_port, "_load_openai_client_class", lambda: _FailingClient)
    logger = _FakeRequestLogger()

    llm = OpenAILLMPort(
        api_key="secret-key",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30.0,
        mapper=OpenAIMapper(usage_mapper=DefaultLLMUsageMapper()),
        request_logger=logger,
    )

    result = llm.generate(_minimax_request(log_request_file="/tmp/skiller-llm.json"))

    assert result.ok is False
    assert result.error == "OpenAI request failed: network down"
    assert logger.requests == [_expected_openai_kwargs()]
    assert logger.responses == []
    assert logger.errors == ["OpenAI request failed: network down"]
