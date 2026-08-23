import inspect
from dataclasses import dataclass

import pytest

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMMessageRole,
    LLMResponse,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUsage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition

pytestmark = pytest.mark.unit


def _model(value: str, context_window_tokens: int) -> LLMModelDefinition:
    return LLMModelDefinition(
        model=value, context_window_tokens=context_window_tokens, max_output_tokens=None
    )


@dataclass(frozen=True)
class _CustomModel:
    value: str
    model_context_window_tokens: int
    max_output_tokens: int | None


def test_llm_message_factories_return_role_specific_messages() -> None:
    tool_call = LLMToolCall(
        id="call-1",
        function=LLMToolCallFunction(
            name="shell",
            arguments_json='{"command":"pwd"}',
        ),
    )

    system = LLMSystemMessage("system")
    user = LLMUserMessage("user")
    assistant = LLMAssistantMessage(tool_calls=(tool_call,))
    tool = LLMToolMessage("result", tool_call_id="call-1")

    assert system.role == LLMMessageRole.SYSTEM
    assert system.content == "system"
    assert user.role == LLMMessageRole.USER
    assert user.content == "user"
    assert assistant.role == LLMMessageRole.ASSISTANT
    assert assistant.tool_calls == (tool_call,)
    assert tool.role == LLMMessageRole.TOOL
    assert tool.tool_call_id == "call-1"


def test_assistant_message_requires_content_or_tool_calls() -> None:
    with pytest.raises(ValueError, match="Assistant messages require content or tool calls"):
        LLMAssistantMessage()


def test_llm_response_normalizes_metadata_strings() -> None:
    response = LLMResponse(
        content=" done ",
        model=_model("model1", 100_000),
        finish_type=LLMFinishType.ERROR_REQUEST_FAILED,
        error=" invalid params ",
        error_code=" 2013 ",
    )

    assert response.content == "done"
    assert response.model == _model("model1", 100_000)
    assert response.error == "invalid params"
    assert response.error_code == "2013"


def test_llm_response_converts_empty_metadata_to_none() -> None:
    response = LLMResponse(
        content=" \n ",
        model=_model("model1", 100_000),
        finish_type=LLMFinishType.ERROR_REQUEST_FAILED,
        error="\n",
        error_code="\t",
    )

    assert response.content is None
    assert response.model == _model("model1", 100_000)
    assert response.error is None
    assert response.error_code is None


def test_llm_response_exposes_semantic_properties() -> None:
    response = LLMResponse(
        model=_model("model1", 100_000),
        finish_type=LLMFinishType.STOP,
        content="done",
    )

    assert response.has_text_content is True
    assert response.has_tool_calls is False


def test_llm_response_requires_finish_type() -> None:
    finish_type = inspect.signature(LLMResponse).parameters["finish_type"]

    assert finish_type.default is inspect.Parameter.empty


def test_llm_usage_normalizes_model_like_values_to_model_name() -> None:
    usage = LLMUsage(
        estimated_system_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        prompt_tokens=None,
        output_tokens=None,
        total_tokens=None,
        provider=None,
        model=_CustomModel(
            value="local/custom",
            model_context_window_tokens=4096,
            max_output_tokens=None,
        ),
    )

    assert usage.model == "local/custom"


def test_llm_usage_rejects_invalid_model_name() -> None:
    with pytest.raises(TypeError, match="LLMUsage model must be a non-empty string"):
        LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            prompt_tokens=None,
            output_tokens=None,
            total_tokens=None,
            provider=None,
            model="",
        )
