import pytest

from skiller.domain.agent.llm.provider_registry import (
    AgentBedrockLLMModel,
    AgentBedrockProvider,
    AgentCodexLLMModel,
    AgentCodexProvider,
    AgentFakeLLMModel,
    AgentLLMProvider,
    AgentLLMProviderList,
    AgentLLMProviderType,
    AgentLMStudioLLMModel,
    AgentLMStudioProvider,
    AgentMiniMaxLLMModel,
    AgentMiniMaxProvider,
    AgentNullLLMModel,
    agent_llm_model_from_value,
)

pytestmark = pytest.mark.unit


def test_agent_llm_provider_list_requires_default_provider() -> None:
    with pytest.raises(RuntimeError, match="Missing default LLM provider config: codex"):
        AgentLLMProviderList(
            default_provider=AgentLLMProviderType.CODEX,
            providers=(_minimax_provider(),),
        )


def test_agent_llm_models_define_model_context_window_tokens() -> None:
    assert AgentNullLLMModel.NULL1.model_context_window_tokens == 100_000
    assert AgentFakeLLMModel.MODEL1.model_context_window_tokens == 100_000
    assert AgentMiniMaxLLMModel.M2_5.model_context_window_tokens == 204_800
    assert AgentMiniMaxLLMModel.M2_7.model_context_window_tokens == 204_800
    assert AgentLMStudioLLMModel.GEMMA_4_12B_QAT.model_context_window_tokens == 131_072
    assert AgentCodexLLMModel.GPT_5_4.model_context_window_tokens == 1_050_000
    assert AgentCodexLLMModel.GPT_5_5.model_context_window_tokens == 1_050_000
    assert AgentBedrockLLMModel.CLAUDE_OPUS_4_6.model_context_window_tokens == 200_000


def test_agent_llm_model_rejects_unsupported_codex_model() -> None:
    assert (
        agent_llm_model_from_value("google/gemma-4-12b-qat")
        == AgentLMStudioLLMModel.GEMMA_4_12B_QAT
    )

    with pytest.raises(ValueError, match="Unsupported LLM model: unsupported-codex"):
        agent_llm_model_from_value("unsupported-codex")


def test_agent_llm_providers_require_typed_model_enum() -> None:
    with pytest.raises(
        TypeError,
        match="MiniMax LLM provider model must be an AgentMiniMaxLLMModel",
    ):
        AgentMiniMaxProvider(
            api_key="secret",
            model=AgentCodexLLMModel.GPT_5_5,
            timeout_seconds=30.0,
            window_width_tokens=1_000_000,
        )

    with pytest.raises(
        TypeError,
        match="Codex LLM provider model must be an AgentCodexLLMModel",
    ):
        AgentCodexProvider(
            credentials_file="/tmp/openai-codex.json",
            model=AgentMiniMaxLLMModel.M2_5,
            timeout_seconds=120.0,
            window_width_tokens=1_000_000,
        )

    with pytest.raises(
        TypeError,
        match="LM Studio LLM provider model must be an AgentLMStudioLLMModel",
    ):
        AgentLMStudioProvider(
            model=AgentMiniMaxLLMModel.M2_5,
            timeout_seconds=30.0,
            window_width_tokens=1_000_000,
        )

    with pytest.raises(
        TypeError,
        match="Bedrock LLM provider model must be an AgentBedrockLLMModel",
    ):
        AgentBedrockProvider(
            profile="claude-bedrock",
            model=AgentMiniMaxLLMModel.M2_5,
            timeout_seconds=30.0,
            window_width_tokens=1_000_000,
        )


def test_bedrock_provider_requires_profile() -> None:
    with pytest.raises(ValueError, match="Bedrock LLM provider requires profile"):
        AgentBedrockProvider(
            profile="   ",
            model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
            timeout_seconds=30.0,
            window_width_tokens=1_000_000,
        )


def test_lmstudio_provider_requires_base_url() -> None:
    with pytest.raises(ValueError, match="LM Studio LLM provider requires base_url"):
        AgentLMStudioProvider(
            base_url="   ",
            model=AgentLMStudioLLMModel.GEMMA_4_12B_QAT,
            timeout_seconds=30.0,
            window_width_tokens=131_072,
        )


def _minimax_provider() -> AgentLLMProvider:
    return AgentMiniMaxProvider(
        api_key="secret",
        model=AgentMiniMaxLLMModel.M2_5,
        timeout_seconds=30.0,
        window_width_tokens=1_000_000,
    )
