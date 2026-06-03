import pytest

from skiller.domain.agent.agent_llm_provider_model import AgentFakeLLMModel
from skiller.domain.agent.llm_model import (
    LLMAssistantMessage,
    LLMMessageRole,
    LLMResponse,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUserMessage,
)

pytestmark = pytest.mark.unit


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
        ok=False,
        content=" done ",
        model=AgentFakeLLMModel.MODEL1,
        finish_reason=" stop ",
        error=" invalid params ",
        error_code=" 2013 ",
    )

    assert response.content == "done"
    assert response.model == AgentFakeLLMModel.MODEL1
    assert response.finish_reason == "stop"
    assert response.error == "invalid params"
    assert response.error_code == "2013"


def test_llm_response_converts_empty_metadata_to_none() -> None:
    response = LLMResponse(
        ok=False,
        content=" \n ",
        model=AgentFakeLLMModel.MODEL1,
        finish_reason="",
        error="\n",
        error_code="\t",
    )

    assert response.content is None
    assert response.model == AgentFakeLLMModel.MODEL1
    assert response.finish_reason is None
    assert response.error is None
    assert response.error_code is None


def test_llm_response_exposes_semantic_properties() -> None:
    response = LLMResponse(ok=False, model=AgentFakeLLMModel.MODEL1, content="done")

    assert response.has_text_content is True
    assert response.has_tool_calls is False
    assert response.is_error is True
