from __future__ import annotations

from dataclasses import dataclass

from openai.types.responses import Response
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_output_message import ResponseOutputMessage
from openai.types.responses.response_output_text import ResponseOutputText

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMResponse, LLMToolCall, LLMToolCallFunction
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.infrastructure.llm.codex.codex_response_model import CodexResponseModel
from skiller.infrastructure.llm.mapper.llm_usage_mapper import (
    LLMProviderUsage,
    LLMUsageMapper,
)


@dataclass(frozen=True)
class ResponsesMapper:
    usage_mapper: LLMUsageMapper

    def to_response(
        self,
        response_model: CodexResponseModel,
        *,
        request: CodexLLMRequest,
    ) -> LLMResponse:
        response = response_model.response
        content = _content(response)
        tool_calls, malformed_error_code = _tool_calls(response)
        finish_type, error, error_code = _finish(
            response=response,
            content=content,
            tool_calls=tool_calls,
            malformed_error_code=malformed_error_code,
        )
        return LLMResponse(
            model=request.model,
            content=content or None,
            tool_calls=tool_calls,
            finish_type=finish_type,
            error=error,
            error_code=error_code,
            usage=self.usage_mapper.to_usage(_usage(response), request=request),
        )


def _content(response: Response) -> str:
    text: list[str] = []
    for output_item in response.output:
        if not isinstance(output_item, ResponseOutputMessage):
            continue
        for content_part in output_item.content:
            if isinstance(content_part, ResponseOutputText):
                text.append(content_part.text)
    return "".join(text)


def _tool_calls(response: Response) -> tuple[tuple[LLMToolCall, ...], str | None]:
    tool_calls: list[LLMToolCall] = []
    for output_item in response.output:
        if not isinstance(output_item, ResponseFunctionToolCall):
            continue
        if not isinstance(output_item.call_id, str) or not output_item.call_id.strip():
            return (), "missing_tool_call_id"
        if not isinstance(output_item.name, str) or not output_item.name.strip():
            return (), "missing_tool_name"
        if not isinstance(output_item.arguments, str):
            return (), "invalid_tool_arguments"
        tool_calls.append(
            LLMToolCall(
                id=output_item.call_id,
                function=LLMToolCallFunction(
                    name=output_item.name,
                    arguments_json=output_item.arguments,
                ),
            )
        )
    return tuple(tool_calls), None


def _finish(
    *,
    response: Response,
    content: str,
    tool_calls: tuple[LLMToolCall, ...],
    malformed_error_code: str | None,
) -> tuple[LLMFinishType, str | None, str | None]:
    if response.status is None:
        return _error(LLMFinishType.ERROR_MISSING_FINISH_REASON, "missing_finish_reason")
    if response.status == "completed":
        if malformed_error_code is not None:
            return _error(LLMFinishType.ERROR_MALFORMED_RESPONSE, malformed_error_code)
        if tool_calls:
            return LLMFinishType.TOOL_CALLS, None, None
        if not content.strip():
            return _error(LLMFinishType.ERROR_MISSING_CONTENT, "missing_content")
        return LLMFinishType.STOP, None, None
    if response.status == "incomplete":
        reason = (
            response.incomplete_details.reason
            if response.incomplete_details is not None
            else None
        )
        if reason == "max_output_tokens":
            return _error(LLMFinishType.INVALID_RESPONSE_LENGTH, "response_length")
        if reason == "content_filter":
            return _error(LLMFinishType.INVALID_RESPONSE_CONTENT_FILTER, "content_filter")
        return _error(LLMFinishType.ERROR_MALFORMED_RESPONSE, "invalid_incomplete_reason")
    if response.status == "failed":
        if response.error is None:
            return _error(LLMFinishType.ERROR_MALFORMED_RESPONSE, "missing_response_error")
        return (
            LLMFinishType.ERROR_REQUEST_FAILED,
            response.error.message,
            response.error.code,
        )
    if response.status in ("queued", "in_progress", "cancelled"):
        return _error(LLMFinishType.ERROR_MALFORMED_RESPONSE, "invalid_response_status")
    return _error(LLMFinishType.UNKNOWN, "unknown_finish_reason")


def _usage(response: Response) -> LLMProviderUsage | None:
    if response.usage is None:
        return None
    input_tokens_details = response.usage.input_tokens_details
    cache_read_tokens = None
    cache_write_tokens = None
    if input_tokens_details is not None:
        cache_read_tokens = getattr(input_tokens_details, "cached_tokens", None)
        cache_write_tokens = getattr(input_tokens_details, "cache_write_tokens", None)
    return LLMProviderUsage(
        prompt_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        total_tokens=response.usage.total_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )


def _error(finish_type: LLMFinishType, error_code: str) -> tuple[LLMFinishType, str, str]:
    return finish_type, f"Codex response {error_code.replace('_', ' ')}", error_code
