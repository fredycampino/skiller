from __future__ import annotations

from types import SimpleNamespace

import pytest

from skiller.domain.agent.llm.model import (
    LLMToolCall,
    LLMToolCallFunction,
)
from skiller.domain.agent.llm.provider_registry import (
    AgentCodexLLMModel,
)
from skiller.infrastructure.llm.codex.codex_mapper import (
    CodexStreamResult,
    to_port_llm_response,
)

pytestmark = pytest.mark.unit


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


def test_to_port_llm_response_maps_final_response_to_port_response() -> None:
    stream_result = CodexStreamResult(
        response=SimpleNamespace(
            model="gpt-5.4",
            status="completed",
            output_text="hello",
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
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

    result = to_port_llm_response(
        stream_result,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
    )

    assert result.ok is True
    assert result.content == "hello"
    assert result.model == AgentCodexLLMModel.GPT_5_4
    assert result.finish_reason == "completed"
    assert result.usage is not None
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
    assert result.usage.total_tokens == 15
    assert result.tool_calls == (
        LLMToolCall(
            id="call_1",
            function=LLMToolCallFunction(
                name="shell",
                arguments_json='{"command":"pwd"}',
            ),
        ),
    )


def test_to_port_llm_response_prefers_streamed_text() -> None:
    stream_result = CodexStreamResult(
        response=SimpleNamespace(
            model="gpt-5.4",
            status="completed",
            output_text="final text",
            output=[],
        ),
        text_deltas=("streamed", " text"),
    )

    result = to_port_llm_response(
        stream_result,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
    )

    assert result.content == "streamed text"


def test_to_port_llm_response_reads_text_from_message_output() -> None:
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

    result = to_port_llm_response(
        stream_result,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
    )

    assert result.content == "hello world"


def test_to_port_llm_response_uses_streamed_output_items_when_final_output_is_empty() -> None:
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

    result = to_port_llm_response(
        stream_result,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
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


def test_to_port_llm_response_tolerates_codex_output_text_with_null_output() -> None:
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

    result = to_port_llm_response(
        stream_result,
        fallback_model=AgentCodexLLMModel.GPT_5_4,
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
