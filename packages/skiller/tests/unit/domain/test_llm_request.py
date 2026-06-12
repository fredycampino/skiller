import pytest

from skiller.domain.agent.agent_llm_generation_model import LLMToolChoiceMode
from skiller.domain.agent.agent_llm_provider_model import (
    AgentBedrockLLMModel,
    AgentCodexLLMModel,
    AgentFakeLLMModel,
    AgentMiniMaxLLMModel,
)
from skiller.domain.agent.llm_model import LLMUserMessage
from skiller.domain.agent.llm_request import (
    BedrockLLMRequest,
    CodexLLMRequest,
    LLMRequest,
    MiniMaxLLMRequest,
)

pytestmark = pytest.mark.unit


def test_llm_request_requires_supported_model() -> None:
    request = LLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=AgentFakeLLMModel.MODEL1,
    )

    assert request.model == AgentFakeLLMModel.MODEL1

    with pytest.raises(TypeError, match="LLMRequest model must be an AgentLLMModel enum"):
        LLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=object(),
        )


def test_minimax_llm_request_requires_minimax_model() -> None:
    request = MiniMaxLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=AgentMiniMaxLLMModel.M2_7,
        tool_choice=LLMToolChoiceMode.AUTO,
        parallel_tool_calls=True,
        temperature=1,
        max_tokens=4096,
        top_p=1,
    )

    assert request.model == AgentMiniMaxLLMModel.M2_7

    with pytest.raises(
        TypeError,
        match="MiniMaxLLMRequest model must be an AgentMiniMaxLLMModel",
    ):
        MiniMaxLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentCodexLLMModel.GPT_5_5,
            tool_choice=LLMToolChoiceMode.AUTO,
            parallel_tool_calls=True,
            temperature=1,
            max_tokens=4096,
            top_p=1,
        )


def test_codex_llm_request_requires_codex_model() -> None:
    request = CodexLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=AgentCodexLLMModel.GPT_5_5,
        parallel_tool_calls=True,
    )

    assert request.model == AgentCodexLLMModel.GPT_5_5

    with pytest.raises(
        TypeError,
        match="CodexLLMRequest model must be an AgentCodexLLMModel",
    ):
        CodexLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentMiniMaxLLMModel.M2_7,
            parallel_tool_calls=True,
        )


def test_bedrock_llm_request_requires_bedrock_model() -> None:
    request = BedrockLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
    )

    assert request.model == AgentBedrockLLMModel.CLAUDE_OPUS_4_6

    with pytest.raises(
        TypeError,
        match="BedrockLLMRequest model must be an AgentBedrockLLMModel",
    ):
        BedrockLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentCodexLLMModel.GPT_5_5,
        )
