from __future__ import annotations

from types import SimpleNamespace

import pytest

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMToolChoiceMode, LLMUserMessage
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.request import OpenAILLMRequest
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper
from skiller.infrastructure.llm.openai import openai_llm_port
from skiller.infrastructure.llm.openai.openai_llm_port import OpenAILLMPort
from skiller.infrastructure.llm.openai.openai_mapper import OpenAIMapper

pytestmark = pytest.mark.unit


class _FakeClient:
    def __init__(self, response: object) -> None:
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: response))


class _FakeRequestLogger:
    def log_request(self, **_kwargs: object) -> None:
        pass

    def log_response(self, **_kwargs: object) -> None:
        pass

    def log_error(self, **_kwargs: object) -> None:
        pass


def _request() -> OpenAILLMRequest:
    return OpenAILLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=LLMModelDefinition(
            model="gpt-4.1", context_window_tokens=1_000_000, max_output_tokens=None
        ),
        tool_choice=LLMToolChoiceMode.AUTO,
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
    )


def _response(*, finish_reason: object = "stop", content: object = "Done.") -> object:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content, tool_calls=[]),
            )
        ]
    )


def _port(response: object) -> OpenAILLMPort[OpenAILLMRequest]:
    return OpenAILLMPort(
        api_key="secret-key",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30,
        mapper=OpenAIMapper(usage_mapper=DefaultLLMUsageMapper()),
        request_logger=_FakeRequestLogger(),
    )


@pytest.mark.parametrize(
    ("raw_response", "expected_finish_type", "expected_error"),
    [
        pytest.param(_response(), LLMFinishType.STOP, None, id="stop"),
        pytest.param(
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="tool_calls",
                        message=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    id="call_1",
                                    function=SimpleNamespace(
                                        name="get_weather",
                                        arguments='{"city":"Madrid"}',
                                    ),
                                )
                            ],
                        ),
                    )
                ]
            ),
            LLMFinishType.TOOL_CALLS,
            None,
            id="tool-calls",
        ),
        pytest.param(
            _response(finish_reason="length", content="Partial answer"),
            LLMFinishType.INVALID_RESPONSE_LENGTH,
            "OpenAI response was truncated due to length",
            id="length",
        ),
        pytest.param(
            _response(finish_reason="content_filter", content=None),
            LLMFinishType.INVALID_RESPONSE_CONTENT_FILTER,
            "OpenAI response was blocked by the content filter",
            id="content-filter",
        ),
        pytest.param(
            SimpleNamespace(choices=[]),
            LLMFinishType.ERROR_MISSING_CHOICES,
            "OpenAI response missing choices",
            id="missing-choices",
        ),
        pytest.param(
            SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=None)]),
            LLMFinishType.ERROR_MISSING_MESSAGE,
            "OpenAI response missing message payload",
            id="missing-message",
        ),
        pytest.param(
            _response(finish_reason=None),
            LLMFinishType.ERROR_MISSING_FINISH_REASON,
            "OpenAI response missing finish reason",
            id="missing-finish-reason",
        ),
        pytest.param(
            _response(content="   "),
            LLMFinishType.ERROR_MISSING_CONTENT,
            "OpenAI response missing content",
            id="missing-content",
        ),
        pytest.param(
            _response(finish_reason="tool_calls", content=None),
            LLMFinishType.ERROR_MISSING_TOOL_CALLS,
            "OpenAI response missing tool calls",
            id="missing-tool-calls",
        ),
        pytest.param(
            _response(finish_reason="function_call", content=None),
            LLMFinishType.ERROR_MISSING_TOOL_CALLS,
            "OpenAI response missing tool calls",
            id="legacy-function-call-without-tool-calls",
        ),
        pytest.param(
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content="Done.",
                            tool_calls=[
                                SimpleNamespace(
                                    id="call_1",
                                    function=SimpleNamespace(
                                        name="get_weather",
                                        arguments='{"city":"Madrid"}',
                                    ),
                                )
                            ],
                        ),
                    )
                ]
            ),
            LLMFinishType.ERROR_MALFORMED_RESPONSE,
            "OpenAI response has an inconsistent finish reason",
            id="stop-with-tool-calls",
        ),
        pytest.param(
            _response(finish_reason="provider_new_reason"),
            LLMFinishType.UNKNOWN,
            "OpenAI response has an unknown finish reason",
            id="unknown-finish-reason",
        ),
    ],
)
def test_openai_llm_port_returns_finish_type_and_error_from_provider_response(
    monkeypatch: pytest.MonkeyPatch,
    raw_response: object,
    expected_finish_type: LLMFinishType,
    expected_error: str | None,
) -> None:
    monkeypatch.setattr(
        openai_llm_port,
        "_load_openai_client_class",
        lambda: lambda **_kwargs: _FakeClient(raw_response),
    )

    response = _port(raw_response).generate(_request())

    assert response.finish_type == expected_finish_type
    assert response.error == expected_error


def test_openai_llm_port_returns_finish_type_and_error_when_api_key_is_missing() -> None:
    port = OpenAILLMPort(
        api_key="",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30,
        mapper=OpenAIMapper(usage_mapper=DefaultLLMUsageMapper()),
        request_logger=_FakeRequestLogger(),
    )

    response = port.generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_API_KEY_MISSING
    assert response.error == "API key is not configured for the selected model provider"


def test_openai_llm_port_returns_finish_type_and_error_when_request_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_request_error(**_kwargs: object) -> object:
        raise RuntimeError("network down")

    failing_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_raise_request_error))
    )
    monkeypatch.setattr(
        openai_llm_port,
        "_load_openai_client_class",
        lambda: lambda **_kwargs: failing_client,
    )

    response = _port(_response()).generate(_request())

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error == "OpenAI request failed: network down"
