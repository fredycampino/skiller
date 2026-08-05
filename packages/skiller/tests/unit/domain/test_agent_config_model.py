import pytest

from skiller.domain.agent.llm.model import LLMCustomModel
from skiller.domain.agent.llm.provider_registry import (
    BEDROCK_MODELS,
    CODEX_MODELS,
    MINIMAX_MODELS,
    AgentBedrockLLMModel,
    AgentBedrockProvider,
    AgentCodexLLMModel,
    AgentCodexProvider,
    AgentFakeLLMModel,
    AgentLLMProvider,
    AgentLLMProviderList,
    AgentLLMProviderType,
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
    assert AgentCodexLLMModel.GPT_5_4.model_context_window_tokens == 1_050_000
    assert AgentCodexLLMModel.GPT_5_5.model_context_window_tokens == 1_050_000
    assert AgentBedrockLLMModel.CLAUDE_OPUS_4_6.model_context_window_tokens == 200_000


def test_agent_llm_model_rejects_unsupported_codex_model() -> None:
    with pytest.raises(ValueError, match="Unsupported LLM model: unsupported-codex"):
        agent_llm_model_from_value("unsupported-codex")


def test_agent_llm_providers_require_typed_model() -> None:
    with pytest.raises(
        TypeError,
        match="MiniMax LLM provider model must be an AgentMiniMaxLLMModel",
    ):
        AgentMiniMaxProvider(
            api_key="secret",
            model=AgentCodexLLMModel.GPT_5_5,
            models=MINIMAX_MODELS,
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
            models=CODEX_MODELS,
            timeout_seconds=120.0,
            window_width_tokens=1_000_000,
        )

    with pytest.raises(
        TypeError,
        match="Bedrock LLM provider model must be an AgentBedrockLLMModel",
    ):
        AgentBedrockProvider(
            profile="claude-bedrock",
            model=AgentMiniMaxLLMModel.M2_5,
            models=BEDROCK_MODELS,
            timeout_seconds=30.0,
            window_width_tokens=1_000_000,
        )


def test_agent_llm_provider_rejects_model_outside_allowed_models() -> None:
    with pytest.raises(
        ValueError,
        match="LLM provider model is not allowed: MiniMax-M2.7",
    ):
        AgentMiniMaxProvider(
            api_key="secret",
            model=AgentMiniMaxLLMModel.M2_7,
            models=(AgentMiniMaxLLMModel.M2_5,),
            timeout_seconds=30.0,
            window_width_tokens=1_000_000,
        )


def test_agent_llm_provider_model_and_context_max_tokens_use_smaller_limit() -> None:
    model = _lmstudio_model()
    config_larger_than_model = AgentLMStudioProvider(
        base_url="http://127.0.0.1:1234/v1",
        model=model,
        models=(model,),
        timeout_seconds=30.0,
        window_width_tokens=200_000,
    )
    config_smaller_than_model = AgentLMStudioProvider(
        base_url="http://127.0.0.1:1234/v1",
        model=model,
        models=(model,),
        timeout_seconds=30.0,
        window_width_tokens=100_000,
    )

    assert config_larger_than_model.model_max_tokens == 131_072
    assert config_larger_than_model.context_max_tokens(ratio=0.8) == 104_857
    assert config_larger_than_model.tool_result_max_bytes == 50_000
    assert config_smaller_than_model.model_max_tokens == 100_000
    assert config_smaller_than_model.context_max_tokens(ratio=0.8) == 80_000
    assert config_smaller_than_model.tool_result_max_bytes == 40_000


def test_bedrock_provider_requires_profile() -> None:
    with pytest.raises(ValueError, match="Bedrock LLM provider requires profile"):
        AgentBedrockProvider(
            profile="   ",
            model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
            models=BEDROCK_MODELS,
            timeout_seconds=30.0,
            window_width_tokens=1_000_000,
        )


def test_lmstudio_provider_requires_base_url() -> None:
    with pytest.raises(ValueError, match="LM Studio LLM provider requires base_url"):
        AgentLMStudioProvider(
            base_url="   ",
            model=_lmstudio_model(),
            models=(_lmstudio_model(),),
            timeout_seconds=30.0,
            window_width_tokens=131_072,
        )


def _minimax_provider() -> AgentLLMProvider:
    return AgentMiniMaxProvider(
        api_key="secret",
        model=AgentMiniMaxLLMModel.M2_5,
        models=MINIMAX_MODELS,
        timeout_seconds=30.0,
        window_width_tokens=1_000_000,
    )


def _lmstudio_model() -> LLMCustomModel:
    return LLMCustomModel(
        value="google/gemma-4-12b-qat",
        model_context_window_tokens=131_072,
    )
