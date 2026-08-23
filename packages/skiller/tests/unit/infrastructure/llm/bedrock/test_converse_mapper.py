from __future__ import annotations

import pytest

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMUserMessage
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.infrastructure.llm.bedrock.converse_mapper import ConverseMapper
from skiller.infrastructure.llm.bedrock.converse_response_model import (
    ConverseContentBlock,
    ConverseMetricsModel,
    ConverseResponseModel,
    ConverseTextContentBlock,
    ConverseToolUseContentBlock,
    ConverseUsageModel,
)
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper

pytestmark = pytest.mark.unit


def _request() -> BedrockLLMRequest:
    return BedrockLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=LLMModelDefinition(model="test", context_window_tokens=1_000, max_output_tokens=None),
    )


def _response(
    *, stop_reason: str | None, content: tuple[ConverseContentBlock, ...]
) -> ConverseResponseModel:
    return ConverseResponseModel(
        role="assistant",
        content=content,
        stop_reason=stop_reason,
        usage=ConverseUsageModel(None, None, None, None, None, ()),
        metrics=ConverseMetricsModel(latency_ms=1),
        stream=(),
    )


@pytest.mark.parametrize(
    ("response", "expected_finish_type"),
    [
        pytest.param(
            _response(stop_reason="end_turn", content=(ConverseTextContentBlock("hello"),)),
            LLMFinishType.STOP,
            id="end-turn-text",
        ),
        pytest.param(
            _response(
                stop_reason="tool_use",
                content=(ConverseToolUseContentBlock("id", "shell", {}),),
            ),
            LLMFinishType.TOOL_CALLS,
            id="tool-use",
        ),
        pytest.param(
            _response(stop_reason="max_tokens", content=()),
            LLMFinishType.INVALID_RESPONSE_LENGTH,
            id="max-tokens",
        ),
        pytest.param(
            _response(stop_reason="content_filtered", content=()),
            LLMFinishType.INVALID_RESPONSE_CONTENT_FILTER,
            id="content-filtered",
        ),
        pytest.param(
            _response(stop_reason=None, content=()),
            LLMFinishType.ERROR_MISSING_FINISH_REASON,
            id="missing-finish-reason",
        ),
        pytest.param(
            _response(stop_reason="end_turn", content=()),
            LLMFinishType.ERROR_MISSING_CONTENT,
            id="missing-content",
        ),
        pytest.param(
            _response(stop_reason="tool_use", content=()),
            LLMFinishType.ERROR_MISSING_TOOL_CALLS,
            id="missing-tool-calls",
        ),
        pytest.param(
            _response(
                stop_reason="end_turn",
                content=(ConverseToolUseContentBlock("id", "shell", {}),),
            ),
            LLMFinishType.ERROR_MALFORMED_RESPONSE,
            id="inconsistent-stop-reason",
        ),
        pytest.param(
            _response(
                stop_reason="tool_use",
                content=(ConverseToolUseContentBlock(None, "shell", {}),),
            ),
            LLMFinishType.ERROR_MALFORMED_RESPONSE,
            id="missing-tool-use-id",
        ),
        pytest.param(
            _response(
                stop_reason="tool_use",
                content=(ConverseToolUseContentBlock("id", None, {}),),
            ),
            LLMFinishType.ERROR_MALFORMED_RESPONSE,
            id="missing-tool-name",
        ),
        pytest.param(
            ConverseResponseModel(
                role="user",
                content=(),
                stop_reason="end_turn",
                usage=ConverseUsageModel(None, None, None, None, None, ()),
                metrics=ConverseMetricsModel(latency_ms=1),
                stream=(),
            ),
            LLMFinishType.ERROR_MALFORMED_RESPONSE,
            id="invalid-role",
        ),
        pytest.param(
            _response(stop_reason="unexpected", content=()),
            LLMFinishType.UNKNOWN,
            id="unknown-stop-reason",
        ),
    ],
)
def test_converse_mapper_maps_finish_type(
    response: ConverseResponseModel,
    expected_finish_type: LLMFinishType,
) -> None:
    mapped = ConverseMapper(usage_mapper=DefaultLLMUsageMapper()).to_response(
        response,
        request=_request(),
    )

    assert mapped.finish_type == expected_finish_type


def test_converse_mapper_includes_cache_tokens_in_prompt_tokens() -> None:
    response = ConverseResponseModel(
        role="assistant",
        content=(ConverseTextContentBlock("hello"),),
        stop_reason="end_turn",
        usage=ConverseUsageModel(
            input_tokens=201,
            output_tokens=1_673,
            total_tokens=66_523,
            cache_read_input_tokens=64_406,
            cache_write_input_tokens=243,
            cache_details=(),
        ),
        metrics=ConverseMetricsModel(latency_ms=1),
        stream=(),
    )

    mapped = ConverseMapper(usage_mapper=DefaultLLMUsageMapper()).to_response(
        response,
        request=_request(),
    )

    assert mapped.usage is not None
    assert mapped.usage.prompt_tokens == 64_850
    assert mapped.usage.output_tokens == 1_673
    assert mapped.usage.total_tokens == 66_523
    assert mapped.usage.cache_read_tokens == 64_406
    assert mapped.usage.cache_write_tokens == 243
