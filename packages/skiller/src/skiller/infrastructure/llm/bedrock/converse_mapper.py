from __future__ import annotations

import json
from dataclasses import dataclass

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMResponse, LLMToolCall, LLMToolCallFunction
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.infrastructure.llm.bedrock.converse_response_model import (
    ConverseResponseModel,
    ConverseTextContentBlock,
)
from skiller.infrastructure.llm.mapper.llm_usage_mapper import (
    LLMProviderUsage,
    LLMUsageMapper,
)


@dataclass(frozen=True)
class ConverseMapper:
    usage_mapper: LLMUsageMapper

    def to_response(
        self,
        response: ConverseResponseModel,
        *,
        request: BedrockLLMRequest,
    ) -> LLMResponse:
        content: list[str] = []
        tool_calls: list[LLMToolCall] = []
        malformed_error_code: str | None = None
        for block in response.content:
            if isinstance(block, ConverseTextContentBlock):
                content.append(block.text)
                continue
            if block.tool_use_id is None or not block.tool_use_id.strip():
                malformed_error_code = "missing_tool_use_id"
                continue
            if block.name is None or not block.name.strip():
                malformed_error_code = "missing_tool_name"
                continue
            tool_calls.append(
                LLMToolCall(
                    id=block.tool_use_id.strip(),
                    function=LLMToolCallFunction(
                        name=block.name.strip(),
                        arguments_json=json.dumps(
                            block.input,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    ),
                )
            )

        finish_type, error, error_code = _finish(
            role=response.role,
            stop_reason=response.stop_reason,
            content="".join(content),
            tool_calls=tuple(tool_calls),
            malformed_error_code=malformed_error_code,
        )
        usage = self.usage_mapper.to_usage(
            LLMProviderUsage(
                prompt_tokens=_total_prompt_tokens(
                    prompt_tokens=response.usage.input_tokens,
                    cache_read_tokens=response.usage.cache_read_input_tokens,
                    cache_write_tokens=response.usage.cache_write_input_tokens,
                ),
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens,
                cache_read_tokens=response.usage.cache_read_input_tokens,
                cache_write_tokens=response.usage.cache_write_input_tokens,
            ),
            request=request,
        )
        return LLMResponse(
            model=request.model,
            content="".join(content) or None,
            tool_calls=tuple(tool_calls),
            finish_type=finish_type,
            error=error,
            error_code=error_code,
            usage=usage,
        )


def _total_prompt_tokens(
    *,
    prompt_tokens: int | None,
    cache_read_tokens: int | None,
    cache_write_tokens: int | None,
) -> int | None:
    if prompt_tokens is None:
        return None
    return prompt_tokens + (cache_read_tokens or 0) + (cache_write_tokens or 0)


def _finish(
    *,
    role: str,
    stop_reason: str | None,
    content: str,
    tool_calls: tuple[LLMToolCall, ...],
    malformed_error_code: str | None,
) -> tuple[LLMFinishType, str | None, str | None]:
    if role != "assistant":
        return _error(LLMFinishType.ERROR_MALFORMED_RESPONSE, "invalid_role")
    if malformed_error_code is not None:
        return _error(LLMFinishType.ERROR_MALFORMED_RESPONSE, malformed_error_code)
    if stop_reason is None:
        return _error(LLMFinishType.ERROR_MISSING_FINISH_REASON, "missing_finish_reason")
    if not stop_reason:
        return _error(LLMFinishType.ERROR_MALFORMED_RESPONSE, "invalid_stop_reason")
    if stop_reason in ("end_turn", "stop_sequence"):
        if tool_calls:
            return _error(LLMFinishType.ERROR_MALFORMED_RESPONSE, "inconsistent_stop_reason")
        if not content.strip():
            return _error(LLMFinishType.ERROR_MISSING_CONTENT, "missing_content")
        return LLMFinishType.STOP, None, None
    if stop_reason == "tool_use":
        if not tool_calls:
            return _error(LLMFinishType.ERROR_MISSING_TOOL_CALLS, "missing_tool_calls")
        return LLMFinishType.TOOL_CALLS, None, None
    if stop_reason in ("max_tokens", "model_context_window_exceeded"):
        return _error(LLMFinishType.INVALID_RESPONSE_LENGTH, "response_length")
    if stop_reason in ("guardrail_intervened", "content_filtered"):
        return _error(LLMFinishType.INVALID_RESPONSE_CONTENT_FILTER, "content_filter")
    if stop_reason in ("malformed_model_output", "malformed_tool_use"):
        return _error(LLMFinishType.ERROR_MALFORMED_RESPONSE, stop_reason)
    return _error(LLMFinishType.UNKNOWN, "unknown_stop_reason")


def _error(finish_type: LLMFinishType, error_code: str) -> tuple[LLMFinishType, str, str]:
    return finish_type, f"Bedrock response {error_code.replace('_', ' ')}", error_code
