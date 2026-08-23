from __future__ import annotations

import pytest
from openai.types.responses import Response
from openai.types.responses.response import IncompleteDetails
from openai.types.responses.response_error import ResponseError
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_output_message import ResponseOutputMessage
from openai.types.responses.response_output_text import ResponseOutputText
from openai.types.responses.response_usage import InputTokensDetails, ResponseUsage

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMToolCall, LLMToolCallFunction, LLMUserMessage
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.infrastructure.llm.codex.codex_response_model import CodexResponseModel
from skiller.infrastructure.llm.codex.responses_mapper import ResponsesMapper
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper

pytestmark = pytest.mark.unit


def _request() -> CodexLLMRequest:
    return CodexLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=LLMModelDefinition(
            model="gpt-5.6", context_window_tokens=1_000, max_output_tokens=None
        ),
        parallel_tool_calls=False,
        session_id="session-1",
    )


def _response(
    *,
    status: str | None,
    output: list[object] | None = None,
    incomplete_reason: str | None = None,
    error: ResponseError | None = None,
) -> Response:
    incomplete_details = None
    if incomplete_reason is not None:
        incomplete_details = IncompleteDetails.model_construct(reason=incomplete_reason)
    return Response.model_construct(
        id="resp_test",
        created_at=0,
        model="gpt-5.6",
        object="response",
        output=output or [],
        parallel_tool_calls=False,
        tool_choice="auto",
        tools=[],
        status=status,
        incomplete_details=incomplete_details,
        error=error,
    )


def _response_model(response: Response) -> CodexResponseModel:
    return CodexResponseModel(response=response, stream=())


def _text(text: str) -> ResponseOutputMessage:
    return ResponseOutputMessage.model_construct(
        id="msg_test",
        content=[ResponseOutputText.model_construct(type="output_text", text=text)],
        role="assistant",
        status="completed",
        type="message",
    )


def _tool_call(*, call_id: object = "call_1", name: object = "shell") -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall.model_construct(
        arguments='{"command":"pwd"}',
        call_id=call_id,
        name=name,
        type="function_call",
    )


def _result(response: Response):
    return ResponsesMapper(usage_mapper=DefaultLLMUsageMapper()).to_response(
        _response_model(response),
        request=_request(),
    )


def test_responses_mapper_maps_completed_text_to_stop() -> None:
    result = _result(_response(status="completed", output=[_text("hello")]))

    assert result.finish_type == LLMFinishType.STOP
    assert result.error is None
    assert result.content == "hello"


def test_responses_mapper_maps_completed_tool_call_to_tool_calls() -> None:
    result = _result(_response(status="completed", output=[_tool_call()]))

    assert result.finish_type == LLMFinishType.TOOL_CALLS
    assert result.error is None
    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command":"pwd"}',
            ),
        ),
    )


def test_responses_mapper_maps_completed_response_without_content_to_missing_content() -> None:
    result = _result(_response(status="completed"))

    assert result.finish_type == LLMFinishType.ERROR_MISSING_CONTENT
    assert result.error_code == "missing_content"


def test_responses_mapper_maps_incomplete_max_output_tokens_to_length() -> None:
    result = _result(_response(status="incomplete", incomplete_reason="max_output_tokens"))

    assert result.finish_type == LLMFinishType.INVALID_RESPONSE_LENGTH
    assert result.error_code == "response_length"


def test_responses_mapper_maps_incomplete_content_filter() -> None:
    result = _result(_response(status="incomplete", incomplete_reason="content_filter"))

    assert result.finish_type == LLMFinishType.INVALID_RESPONSE_CONTENT_FILTER
    assert result.error_code == "content_filter"


def test_responses_mapper_maps_incomplete_response_without_reason_to_malformed() -> None:
    result = _result(_response(status="incomplete"))

    assert result.finish_type == LLMFinishType.ERROR_MALFORMED_RESPONSE
    assert result.error_code == "invalid_incomplete_reason"


def test_responses_mapper_maps_failed_response_error() -> None:
    error = ResponseError.model_construct(code="server_error", message="provider failed")
    result = _result(_response(status="failed", error=error))

    assert result.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert result.error == "provider failed"
    assert result.error_code == "server_error"


def test_responses_mapper_maps_failed_response_without_error_to_malformed() -> None:
    result = _result(_response(status="failed"))

    assert result.finish_type == LLMFinishType.ERROR_MALFORMED_RESPONSE
    assert result.error_code == "missing_response_error"


def test_responses_mapper_maps_response_without_status_to_missing_finish_reason() -> None:
    result = _result(_response(status=None))

    assert result.finish_type == LLMFinishType.ERROR_MISSING_FINISH_REASON
    assert result.error_code == "missing_finish_reason"


def test_responses_mapper_maps_non_terminal_status_to_malformed() -> None:
    result = _result(_response(status="in_progress"))

    assert result.finish_type == LLMFinishType.ERROR_MALFORMED_RESPONSE
    assert result.error_code == "invalid_response_status"


def test_responses_mapper_maps_unknown_status_to_unknown() -> None:
    result = _result(_response(status="unexpected"))

    assert result.finish_type == LLMFinishType.UNKNOWN
    assert result.error_code == "unknown_finish_reason"


def test_responses_mapper_maps_completed_response_with_malformed_tool_call() -> None:
    result = _result(_response(status="completed", output=[_tool_call(call_id=None)]))

    assert result.finish_type == LLMFinishType.ERROR_MALFORMED_RESPONSE
    assert result.error_code == "missing_tool_call_id"


def test_responses_mapper_accepts_usage_without_input_token_details() -> None:
    usage = ResponseUsage.model_construct(
        input_tokens=10,
        input_tokens_details=None,
        output_tokens=5,
        output_tokens_details=None,
        total_tokens=15,
    )
    response = _response(status="completed", output=[_text("hello")])
    response = response.model_copy(update={"usage": usage})

    result = _result(response)

    assert result.usage is not None
    assert result.usage.prompt_tokens == 10
    assert result.usage.output_tokens == 5
    assert result.usage.cache_read_tokens is None
    assert result.usage.cache_write_tokens is None


def test_responses_mapper_accepts_partial_input_token_details() -> None:
    input_tokens_details = InputTokensDetails.model_construct(cached_tokens=4)
    usage = ResponseUsage.model_construct(
        input_tokens=10,
        input_tokens_details=input_tokens_details,
        output_tokens=5,
        output_tokens_details=None,
        total_tokens=15,
    )
    response = _response(status="completed", output=[_text("hello")])
    response = response.model_copy(update={"usage": usage})

    result = _result(response)

    assert result.usage is not None
    assert result.usage.cache_read_tokens == 4
    assert result.usage.cache_write_tokens is None
