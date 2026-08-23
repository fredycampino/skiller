from __future__ import annotations

from types import SimpleNamespace

import pytest

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMToolChoiceMode, LLMUserMessage
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.request import OpenAILLMRequest
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper
from skiller.infrastructure.llm.openai.openai_mapper import OpenAIMapper

pytestmark = pytest.mark.unit


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


@pytest.mark.parametrize(
    ("raw_response", "expected_finish_type"),
    [
        pytest.param(_response(), LLMFinishType.STOP, id="stop"),
        pytest.param(
            _response(finish_reason="length", content="Partial answer"),
            LLMFinishType.INVALID_RESPONSE_LENGTH,
            id="length",
        ),
        pytest.param(
            _response(finish_reason="content_filter", content=None),
            LLMFinishType.INVALID_RESPONSE_CONTENT_FILTER,
            id="content-filter",
        ),
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
            id="tool-calls",
        ),
        pytest.param(
            _response(finish_reason="function_call", content=None),
            LLMFinishType.ERROR_MISSING_TOOL_CALLS,
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
            id="stop-with-tool-calls",
        ),
        pytest.param(
            SimpleNamespace(choices=[]),
            LLMFinishType.ERROR_MISSING_CHOICES,
            id="missing-choices",
        ),
        pytest.param(
            SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=None)]),
            LLMFinishType.ERROR_MISSING_MESSAGE,
            id="missing-message",
        ),
        pytest.param(
            _response(finish_reason=None),
            LLMFinishType.ERROR_MISSING_FINISH_REASON,
            id="null-finish-reason",
        ),
        pytest.param(
            {"choices": [{"message": {"content": "Done."}}]},
            LLMFinishType.ERROR_MISSING_FINISH_REASON,
            id="missing-finish-reason",
        ),
        pytest.param(
            _response(content="   "),
            LLMFinishType.ERROR_MISSING_CONTENT,
            id="missing-content",
        ),
        pytest.param(
            _response(finish_reason="tool_calls", content=None),
            LLMFinishType.ERROR_MISSING_TOOL_CALLS,
            id="missing-tool-calls",
        ),
        pytest.param(
            _response(finish_reason="provider_new_reason"),
            LLMFinishType.UNKNOWN,
            id="unknown-finish-reason",
        ),
    ],
)
def test_openai_mapper_maps_finish_type(
    raw_response: object,
    expected_finish_type: LLMFinishType,
) -> None:
    response = OpenAIMapper(usage_mapper=DefaultLLMUsageMapper()).to_response(
        raw_response,
        request=_request(),
    )

    assert response.finish_type == expected_finish_type
