from __future__ import annotations

from types import SimpleNamespace

import pytest

from skiller.domain.agent.llm.model import (
    LLMToolCall,
    LLMToolCallFunction,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.infrastructure.llm.codex.codex_mapper import (
    CodexMapper,
    CodexStreamResult,
)
from skiller.infrastructure.llm.codex.codex_model_capabilities import (
    CodexModelCapabilitiesResolver,
)
from skiller.infrastructure.llm.codex.responses_general_mapper import (
    ResponsesGeneralMapper,
)
from skiller.infrastructure.llm.codex.responses_lite_mapper import ResponsesLiteMapper
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper

pytestmark = pytest.mark.unit


def _model(value: str, context_window_tokens: int) -> LLMModelDefinition:
    return LLMModelDefinition(model=value, context_window_tokens=context_window_tokens)


class _ResponseWithBrokenOutputText:
    model = "gpt-5.4"
    status = "completed"
    output = None
    usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
    )

    @property
    def output_text(self) -> str:
        raise TypeError("'NoneType' object is not iterable")


def test_codex_mapper_maps_final_response_to_port_response() -> None:
    stream_result = CodexStreamResult(
        response=SimpleNamespace(
            model="gpt-5.4",
            status="completed",
            output_text="hello",
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                input_tokens_details=SimpleNamespace(
                    cached_tokens=8,
                    cache_write_tokens=2,
                ),
            ),
            output=[
                SimpleNamespace(
                    type="function_call",
                    call_id="call_1",
                    name="shell",
                    arguments='{"command":"pwd"}',
                )
            ],
        )
    )

    result = _mapper().to_response(
        stream_result,
        request=_request(),
    )

    assert result.ok is True
    assert result.content == "hello"
    assert result.model == _model("gpt-5.4", 1_050_000)
    assert result.finish_reason == "completed"
    assert result.usage is not None
    assert result.usage.prompt_tokens == 10
    assert result.usage.estimated_system_tokens == 0
    assert result.usage.output_tokens == 5
    assert result.usage.total_tokens == 15
    assert result.usage.cache_read_tokens == 8
    assert result.usage.cache_write_tokens == 2
    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command":"pwd"}',
            ),
        ),
    )


def test_codex_mapper_prefers_streamed_text() -> None:
    stream_result = CodexStreamResult(
        response=SimpleNamespace(
            model="gpt-5.4",
            status="completed",
            output_text="final text",
            output=[],
        ),
        text_deltas=("streamed", " text"),
    )

    result = _mapper().to_response(
        stream_result,
        request=_request(),
    )

    assert result.content == "streamed text"


def test_codex_mapper_reads_text_from_message_output() -> None:
    stream_result = CodexStreamResult(
        response={
            "model": "gpt-5.4",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "hello"},
                        {"type": "output_text", "text": " world"},
                    ],
                }
            ],
        }
    )

    result = _mapper().to_response(
        stream_result,
        request=_request(),
    )

    assert result.content == "hello world"


def test_codex_mapper_uses_streamed_output_items_when_final_output_is_empty() -> None:
    stream_result = CodexStreamResult(
        response=SimpleNamespace(model="gpt-5.4", status="completed", output=[]),
        output_items=(
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "shell",
                "arguments": {"command": "pwd"},
            },
        ),
    )

    result = _mapper().to_response(
        stream_result,
        request=_request(),
    )

    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command": "pwd"}',
            ),
        ),
    )


def test_codex_mapper_tolerates_codex_output_text_with_null_output() -> None:
    stream_result = CodexStreamResult(
        response=_ResponseWithBrokenOutputText(),
        output_items=(
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "shell",
                "arguments": {"command": "pwd"},
            },
        ),
    )

    result = _mapper().to_response(
        stream_result,
        request=_request(),
    )

    assert result.ok is True
    assert result.content is None
    assert result.usage is not None
    assert result.usage.total_tokens == 15
    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command": "pwd"}',
            ),
        ),
    )


def _request() -> CodexLLMRequest:
    return CodexLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=_model("gpt-5.4", 1_050_000),
        parallel_tool_calls=True,
        session_id="context-1",
    )


def _mapper() -> CodexMapper:
    return CodexMapper(
        usage_mapper=DefaultLLMUsageMapper(),
        capabilities_resolver=CodexModelCapabilitiesResolver(),
        responses_mapper=ResponsesGeneralMapper(),
        responses_lite_mapper=ResponsesLiteMapper(),
    )
